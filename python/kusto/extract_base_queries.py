"""
This script extracts Kusto queries from an Azure Data Explorer dashboard export file.
It is used to extract base queries into a format that can be stored in version control. 

Dashboard exports follow this schema: https://dataexplorer.azure.com/static/d/schema/60/dashboard.json

Usage: extract_base_queries.py [-h] [--output OUTPUT] [--function_folder FUNCTION_FOLDER] dashboard_file
"""
import json
from pathlib import Path
from typing import Dict, Set
from datetime import datetime

# Cache for used parameters to avoid redundant calculations
QUERY_PARAMETERS: Dict[str, Set[str]] = {}

# What default values to use for each parameter type in Kusto
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

def parameters_for_query(
    base_queries_by_name, 
    parameters_by_name,
    queries_by_id,
    query_id
) -> list[tuple[str, str]]:
    """
    if this query were a function, what parameters would it take?
    
    Args:
        base_queries_by_name: Dictionary mapping variable names to base queries
        parameters_by_name: Dictionary mapping parameter names to parameter objects
        queries_by_id: Dictionary mapping query IDs to query objects
        query_id: ID of the query to analyze
        
    Returns:
        List of tuples (parameter_name, parameter_type) for the query, with timestamps sorted to the end
    """
    def get_used_parameters(
        base_queries_by_name, 
        queries_by_id, 
        query_id, 
        in_progress=None
        ) -> Set[str]:
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

    names = get_used_parameters(base_queries_by_name, queries_by_id, query_id)
    return [(p, parameters_by_name[p]["kind"].lower()) for p in sorted(names) if p not in ('_startTime', '_endTime')] \
         + [(p, "datetime") for p in sorted(names, reverse=True) if p in ('_startTime', '_endTime')]

def function_signature(
    function_name: str, 
    parameters: list[tuple[str, str]]
) -> str:
    param_str = ', '.join(name for name, _ in parameters)
    return f"{function_name}({param_str})"

def generate_kusto_function(
        bq_name, 
        query_text, 
        query_parameters, 
        docstring, 
        function_folder
        ):
    # Collect parameter information for function declaration
    function_parameters = [f"{p}:{p_type}" for p, p_type in query_parameters]

    # Create function docstring with description of parameters
    params = "\n    " + ',\n    '.join(function_parameters) + "\n" if function_parameters else ''

    # Build the function creation command using list join approach for better readability
    function_lines = [
        f'.create-or-alter function {bq_name} with (',
        f'  docstring="{docstring}",',
        f'  folder="{function_folder}"',
        f')',
        f"{bq_name}({params}){{",
        query_text,
        "}"
    ]
    
    return '\n'.join(function_lines)

def generate_kusto_query(
        bq_name, 
        query_text, 
        query_parameters
        ):
    # Create let statements for parameters
    parameter_initializations = [
        f"let {p} = {KUSTO_DEFAULT_VALUES.get(p_type, 'dynamic(null)')};" 
        for p, p_type in query_parameters
    ]
    
    # Build query with components
    query_lines = []

    # Add parameter initializations if they exist
    if parameter_initializations:
        query_lines.append(f"// Parameters -- begin")
        query_lines.extend(parameter_initializations)
        query_lines.append(f"// Parameters -- end")
        query_lines.append("//")  # Empty line for separation
        
    query_lines.append(f"// {bq_name} -- begin")
    query_lines.append(query_text)
    query_lines.append(f"// {bq_name} -- end")
    return '\n'.join(query_lines)

def generate_yaml_function(
        bq_name, 
        query_text, 
        query_parameters, 
        docstring, 
        function_folder
        ):
    # Format the query body to maintain proper indentation
    # Strip any leading/trailing whitespace and ensure consistent line endings
    query_body = query_text.strip()
    
    # Process parameters if they exist
    params = ','.join([f"{p}:{p_type}" for p, p_type in query_parameters]) if query_parameters else ''
    
    # Build the YAML document
    yaml_lines = [
        f"name: {bq_name}",
        f"folder: {function_folder}",
        f"docString: {docstring}",
        f"parameters: {params}",
        "body: |-"
    ]
    
    # Add indented query body with proper YAML block scalar formatting
    for line in query_body.split('\n'):
        yaml_lines.append(f"  {line}")
    
    return '\n'.join(yaml_lines)

def extract(
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
    dashboard_title = dashboard.get('title', 'Unknown Dashboard')
    
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
        
        # What parameters do we need for this query?
        query_parameters = parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, query_id)
        query_text = query.get('text', '')

        # Build a version of the query text where base queries are replaced with function calls
        query_text_with_functions = str(query_text)
        for function_name in query.get('usedVariables', []):
            if function_name not in base_queries_by_name:
                continue
            bq = base_queries_by_name[function_name]
            bq_query_id = bq.get('queryId')
            if not bq_query_id:
                continue

            # Replace variable with function call
            sig = function_signature(function_name, parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, bq_query_id))
            query_text_with_functions = query_text_with_functions.replace(function_name, sig)

        # Get query name from variable name
        bq_name = base_query.get('variableName', f'unknown_{base_query_id}')
        timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        docstring=f"{bq_name} exported from dashboard {dashboard_title} on {timestamp}"

        # generate the output contents
        def save(path, content):
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
                if not content.endswith('\n'):
                    f.write('\n')  # Ensure the file ends with a newline

        # functions
        final_text = generate_kusto_function(
            bq_name=bq_name,
            query_text=query_text_with_functions,
            query_parameters=query_parameters,
            docstring=docstring,
            function_folder=function_folder
        )
        save(output_path / "functions" / f"create_{bq_name}.kql", final_text)

        # yaml functions
        final_text = generate_yaml_function(
            bq_name=bq_name,
            query_text=query_text_with_functions,
            query_parameters=query_parameters,
            docstring=docstring,
            function_folder=function_folder
        )
        save(output_path / "yaml" / f"{bq_name}.yaml", final_text)
        
        # bq-style raw queries
        final_text = generate_kusto_query(
            bq_name=bq_name,
            query_text=query_text,
            query_parameters=query_parameters
        )
        save(output_path / "queries" / f"{bq_name}.kusto", final_text)
    
        processed_count += 1
    print(f"Extracted {processed_count} base queries from dashboard '{dashboard_file_path}' into '{output_folder}'")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Extract Kusto queries from Azure Data Explorer dashboard export")
    parser.add_argument("dashboard_file", help="Path to the dashboard JSON file")
    parser.add_argument("--output", "-o", default="extracted", help="Where to save the extracted queries")
    parser.add_argument("--function_folder", "-ff", default="extracted", help="Where to create functions in the kusto database's /functions dir")
    args = parser.parse_args()
    
    extract(
        args.dashboard_file, 
        args.output,
        args.function_folder
    )