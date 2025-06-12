import json
from pathlib import Path
from typing import Dict, Set

# This will hold the dependencies between queries and their used variables
QUERY_PARAMETERS: Dict[str, Set[str]] = {}

# Dictionary mapping parameter types to their default values in Kusto syntax
KUSTO_DEFAULT_VALUES = {
    'string': '""',               # Empty string
    'long': '0',                  # Integer zero
    'int': '0',                   # Integer zero
    'double': '0.0',              # Float zero
    'boolean': 'false',           # Boolean false
    'datetime': 'datetime(null)', # Null datetime
    'timespan': 'timespan(0)',    # Zero timespan
    'dynamic': 'dynamic({})'      # Empty dynamic object
}

def get_used_parameters(base_queries_by_name, queries_by_id, query_id, in_progress=None) -> Set[str]:
    """
    Recursively find all parameters used by a query, accounting for dependencies on other queries.
    
    Args:
        base_queries_by_name: Dictionary mapping variable names to base queries
        queries_by_id: Dictionary mapping query IDs to query objects
        query_id: ID of the query to analyze
        in_progress: Set of query IDs currently being processed (for cycle detection)
        
    Returns:
        Set of parameter names used by this query and its dependencies
    """
    global QUERY_PARAMETERS
    
    # Return cached result if available
    if query_id in QUERY_PARAMETERS:
        return QUERY_PARAMETERS[query_id]
    
    # Initialize in-progress queries set if not provided
    if in_progress is None:
        in_progress = set()
    
    # Prevent circular dependencies
    if query_id in in_progress:
        print(f"Warning: Circular dependency detected for query ID {query_id}")
        return set()  # Return empty set for circular references
    
    # Mark this query as in-progress
    in_progress.add(query_id)
    
    # Get the query and initialize parameters
    query = queries_by_id.get(query_id)
    if query is None:
        print(f"Warning: Query ID {query_id} not found")
        in_progress.remove(query_id)  # Remove from in-progress set before returning
        return set()
    
    parameters = set()
    text = query.get('text', '')
    
    # Check for _startTime and _endTime in used variables in query text
    if '_startTime' in text:
        parameters.add('_startTime')
    if '_endTime' in text:
        parameters.add('_endTime')
    
    # Process each used variable
    for var in query.get('usedVariables', []):
        if var in base_queries_by_name:
            bq = base_queries_by_name[var]
            bq_query_id = bq.get('queryId')
            if not bq_query_id:
                continue
            parameters.update(get_used_parameters(
                base_queries_by_name, 
                queries_by_id, 
                bq_query_id, 
                in_progress
            ))
        else:
            # Otherwise, it's a parameter
            parameters.add(var)

    # Cache results for future calls
    QUERY_PARAMETERS[query_id] = parameters
    
    # Remove from in-progress set now that we're done with this branch
    in_progress.remove(query_id)
    
    return parameters

def get_parameters_for_query(
    base_queries_by_name, 
    parameters_by_name,
    queries_by_id,
    query_id
) -> list[tuple[str, str]]:
    names = get_used_parameters(base_queries_by_name, queries_by_id, query_id)
    return [(p, parameters_by_name[p]["kind"].lower()) for p in sorted(names) if p not in ('_startTime', '_endTime')] \
         + [(p, "datetime") for p in sorted(names, reverse=True) if p in ('_startTime', '_endTime')]

def function_signature(
    function_name: str, 
    parameters: list[tuple[str, str]]
) -> str:
    param_str = ', '.join(name for name, _ in parameters)
    return f"{function_name}({param_str})"

def generate_kusto_function(bq_name, query_text, query_parameters, datasource_name, function_folder):
    # Collect parameter information for function declaration
    function_parameters = [f"{p}:{p_type}" for p, p_type in query_parameters]

    # Create function docstring with description of parameters
    func_description = f"Query extracted from '{datasource_name}' dashboard"
    params = "\n    " + ',\n    '.join(function_parameters) + "\n" if function_parameters else ''

    # Build the function creation command using list join approach for better readability
    function_lines = [
        f'.create-or-alter function {bq_name} with (',
        f'  docstring="{func_description}",',
        f'  folder="{function_folder}"',
        f')',
        f"{bq_name}({params}){{",
        query_text,
        "}"
    ]
    
    return '\n'.join(function_lines)

def generate_kusto_query(bq_name, query_text, query_parameters, datasource_name):
    # Create let statements for parameters
    parameter_initializations = [
        f"let {p} = {KUSTO_DEFAULT_VALUES.get(p_type, 'dynamic(null)')};" 
        for p, p_type in query_parameters
    ]
    
    # Build query with components
    query_lines = [
        f"// database(\"{datasource_name}\").{bq_name}",
        "//",
    ]
    
    # Add parameter initializations if they exist
    if parameter_initializations:
        query_lines.extend(parameter_initializations)
        query_lines.append("")  # Empty line for separation
    
    query_lines.extend([
        "//",
        query_text
    ])
    
    return '\n'.join(query_lines)

def generate_yaml_function(bq_name, query_text, query_parameters, datasource_name, function_folder):
    # Create function docstring with description of parameters
    doc_string = f"Query extracted from '{datasource_name}' dashboard"
    
    # Format the query body to maintain proper indentation
    # Strip any leading/trailing whitespace and ensure consistent line endings
    query_body = query_text.strip()
    
    # Process parameters if they exist
    params = ','.join([f"{p}:{p_type}" for p, p_type in query_parameters]) if query_parameters else ''
    
    # Build the YAML document
    yaml_lines = [
        f"name: {bq_name}",
        f"folder: {function_folder}",
        f"docString: {doc_string}",
        f"parameters: {params}",
        "body: |-"
    ]
    
    # Add indented query body with proper YAML block scalar formatting
    for line in query_body.split('\n'):
        yaml_lines.append(f"  {line}")
    
    return '\n'.join(yaml_lines)

def extract_kusto_queries(
        dashboard_file_path, 
        output_folder='extracted',
        function_folder='extracted',
        ):
    """
    Extract Kusto queries from Azure Data Explorer dashboard export file.
    
    Args:
        dashboard_file_path: Path to the dashboard JSON file
        output_folder: Folder to save extracted queries in
        create_functions: If True, convert each base query into a Kusto function
        function_folder: Folder name to use in the function docstring and creation command
        create_yaml_functions: If True, generate functions in YAML format instead of KQL
    """
    # Create output folder if it doesn't exist
    output_path = Path(output_folder)
    output_path.mkdir(exist_ok=True)
    
    print(f"Loading dashboard file: {dashboard_file_path}")
    with open(dashboard_file_path, 'r') as f:
        dashboard = json.load(f)
    
    # Create lookup dictionaries for quick access
    base_queries_by_id = {}
    base_queries_by_query_id = {}
    base_queries_by_name = {}
    queries_by_id = {}
    datasources_by_id = {}
    parameters_by_name = {}
    
    # First, create lookup tables for all elements
    for base_query in dashboard.get('baseQueries', []):
        base_queries_by_id[base_query['id']] = base_query
        base_queries_by_query_id[base_query['queryId']] = base_query
        base_queries_by_name[base_query.get('variableName', f'unknown_{base_query["id"]}')] = base_query

    for query in dashboard.get('queries', []):
        queries_by_id[query['id']] = query
    
    for datasource in dashboard.get('dataSources', []):
        datasources_by_id[datasource['id']] = datasource
    
    # Map all parameters by their variable name for lookup
    for param in dashboard.get('parameters', []):
        if 'variableName' in param:
            parameters_by_name[param['variableName']] = param
        
    # Keep track of what we've processed
    processed_count = 0

    # Process each base query
    for base_query_id, base_query in base_queries_by_id.items():
        query_id = base_query.get('queryId')
        if not query_id or query_id not in queries_by_id:
            print(f"Warning: No matching query found for base query ID {base_query_id}")
            continue
        
        query = queries_by_id[query_id]
        datasource_info = query.get('dataSource', {})
        datasource_id = datasource_info.get('dataSourceId')
        
        if not datasource_id or datasource_id not in datasources_by_id:
            print(f"Warning: No data source found for query ID {query_id}")
            continue
        
        # Create folder for this datasource
        datasource_name = datasources_by_id[datasource_id]["name"]
        
        # what parameters do we need for this query?
        query_parameters = get_parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, query_id)

        # Get the query text and used variables
        query_text = query.get('text', '')

        # replace any used variables in this query with a function call
        for var in query.get('usedVariables', []):
            if var not in base_queries_by_name:
                continue
            bq = base_queries_by_name[var]
            bq_query_id = bq.get('queryId')
            if not bq_query_id:
                continue

            # Replace variable with function call
            sig = function_signature(var, get_parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, bq_query_id))
            query_text = query_text.replace(var, sig)

        # Get query name from variable name
        bq_name = base_query.get('variableName', f'unknown_{base_query_id}')
        
        # generate the output contents
        datasource_folder = output_path
        def save(path, content):
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)

        final_text = generate_kusto_function(
            bq_name=bq_name,
            query_text=query_text,
            query_parameters=query_parameters,
            datasource_name=datasource_name,
            function_folder=function_folder
        )
        save(datasource_folder / "functions" / f"create_{bq_name}.kql", final_text)

        final_text = generate_yaml_function(
            bq_name=bq_name,
            query_text=query_text,
            query_parameters=query_parameters,
            datasource_name=datasource_name,
            function_folder=function_folder
        )
        save(datasource_folder / "yaml" / f"{bq_name}.yaml", final_text)
            
        final_text = generate_kusto_query(
            bq_name=bq_name,
            query_text=query_text,
            query_parameters=query_parameters,
            datasource_name=datasource_name
        )
        save(datasource_folder / "queries" / f"{bq_name}.kusto", final_text)
    
        processed_count += 1
    print(f"Extracted {processed_count} base queries from dashboard '{dashboard_file_path}' into '{output_folder}'")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Extract Kusto queries from Azure Data Explorer dashboard export")
    parser.add_argument("dashboard_file", help="Path to the dashboard JSON file")
    parser.add_argument("--output", "-o", default="extracted", help="Where to save the extracted queries")
    parser.add_argument("--functions", "-f", action="store_true", help="Generate Kusto functions instead of queries")
    parser.add_argument("--yaml", "-y", action="store_true", help="Generate functions in YAML format")
    parser.add_argument("--function_folder", "-ff", default="extracted", help="Where to create functions in the kusto database's /functions dir")
    args = parser.parse_args()
    
    extract_kusto_queries(
        args.dashboard_file, 
        args.output,
        function_folder=args.function_folder
    )