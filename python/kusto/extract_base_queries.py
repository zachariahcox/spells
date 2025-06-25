"""
This script extracts Kusto queries from an Azure Data Explorer dashboard export file.
It is used to extract base queries into a format that can be stored in version control. 

Dashboard exports follow this schema: https://dataexplorer.azure.com/static/d/schema/60/dashboard.json

Usage: extract_base_queries.py [-h] [--output OUTPUT] [--function_folder FUNCTION_FOLDER] dashboard_file
"""
import json
from pathlib import Path
import re
from typing import Dict, Set
from datetime import datetime

# Cache for used parameters to avoid redundant calculations
QUERY_PARAMETERS: Dict[str, Set[str]] = {}

# What default values to use for each parameter type in Kusto
KUSTO_DEFAULT_VALUES = {
    'string': '""',               # Empty string
    'long': 'long(0)',            # Integer zero
    'int': 'int(0)',              # Integer zero
    'real': 'real(0.0)',          # Real zero
    'double': 'double(0.0)',      # Float zero
    'boolean': 'false',           # Boolean false
    'datetime': 'datetime(null)', # Null datetime
    'timespan': 'timespan(0)',    # Zero timespan
    'dynamic': 'dynamic(null)'      # Empty dynamic object
}

def get_default_value(param_type, selection_type) -> str:
    if selection_type != 'scalar':
        return "dynamic(null)" # return dynamic(null) for any list
    if param_type == "time_range":
        return ""
    return KUSTO_DEFAULT_VALUES.get(param_type, 'dynamic(null)')

def parameters_for_query(
    base_queries_by_name, 
    parameters_by_name,
    queries_by_id,
    query_id
) -> list[tuple[str, str, str]]:
    """
    if this query were a function, what parameters would it take?
    
    Args:
        base_queries_by_name: Dictionary mapping variable names to base queries
        parameters_by_name: Dictionary mapping parameter names to parameter objects
        queries_by_id: Dictionary mapping query IDs to query objects
        query_id: ID of the query to analyze
        
    Returns:
        List of tuples (parameter_name, parameter_type, selection_type) for the query, with range start and ends sorted to the beginning
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
    return [(p, 'datetime', "time_range") for p in sorted(names, reverse=True) if p in ('_startTime', '_endTime')] + \
           [(p, parameters_by_name[p]["kind"].lower(), parameters_by_name[p]["selectionType"].lower()) for p in sorted(names) if p not in ('_startTime', '_endTime')]

def function_signature(
    function_name: str, 
    parameters: list[tuple[str, str, str]]
) -> str:
    arguments = ', '.join(name for name, _, _ in parameters)
    return f"{function_name}({arguments})"

def get_range_initializers(query_parameters):
    range_initializers = []
    if '_startTime' in [p for p, _, _ in query_parameters]:
            range_initializers.append(f"let _startTime = coalesce(s, startofday(ago(7d)));")
    if '_endTime' in [p for p, _, _ in query_parameters]:
        range_initializers.append(f"let _endTime = coalesce(e, endofday(now()));")
    return range_initializers

def get_argument_name_for_parameter(param_name: str) -> str:
    if param_name == '_startTime':
        return 'startTime'
    if param_name == '_endTime':
        return 'endTime'
    return param_name

def generate_kusto_function(
    function_name: str,
    query_text: str,
    query_parameters: list[tuple[str, str, str]],
    docstring: str,
    function_folder: str
) -> str:
    lines = [
        f'.create-or-alter function {function_name} with (',
        f'  docstring="{docstring}",',
        f'  folder="{function_folder}"',
        f')'
        ]
    
    # build signature
    function_parameters = ""
    range_initializers = []
    if query_parameters:
        separator = f',\n{4 * " "}'
        params = [f"{get_argument_name_for_parameter(p)}:{p_type}={get_default_value(p_type, p_selection)}"
                  for p, p_type, p_selection in query_parameters]
        function_parameters += separator + separator.join(params) + "\n"
        range_initializers = get_range_initializers(query_parameters)

    # build function body
    lines.append(f"{function_name}({function_parameters}){{")
    if range_initializers:
        lines.append("\n".join(range_initializers))
    lines.append(query_text)
    lines.append(f"}}")

    return '\n'.join(lines)

def generate_kusto_query(
    bq_name: str,
    query_text: str,
    query_parameters: list[tuple[str, str, str]]
) -> str:
    # Build query with components
    query_lines = []

    # Add parameter initializations if they exist
    if query_parameters:
        # Create let statements for parameters
        parameter_initializations = [
            f"let {p} = {get_default_value(p_type, p_selection)};"
            for p, p_type, p_selection in query_parameters
        ]
        query_lines.append(f"// Parameters -- begin")
        query_lines.extend(parameter_initializations)
        query_lines.append(f"// Parameters -- end")
        query_lines.append("//")  # Empty line for separation
        
    query_lines.append(f"// {bq_name} -- begin")
    query_lines.append(query_text)
    query_lines.append(f"// {bq_name} -- end")
    return '\n'.join(query_lines)

def generate_yaml_function(
    function_name: str,
    query_text: str,
    query_parameters: list[tuple[str, str, str]],
    docstring: str,
    function_folder: str
) -> str:
    # Build the YAML document
    yaml_lines = [
        f"folder: {function_folder}",
        f"docString: {docstring}",
        f"preformatted: true", # should be preformatted to work with KustoSchemaTools https://github.com/github/KustoSchemaTools
    ]

    # Reference parameters if needed
    if query_parameters:
        # Create a comma-separated list of parameters with their default values
        params = ','.join([f"{get_argument_name_for_parameter(p)}:{p_type}={get_default_value(p_type, p_selection)}"
                           for p, p_type, p_selection in query_parameters])
        yaml_lines.append(f"parameters: {params}")
    
    # Format the query body to maintain proper indentation
    # Strip any leading/trailing whitespace and ensure consistent line endings
    query_body = query_text.strip()
    range_initializers = get_range_initializers(query_parameters)
    if range_initializers:
        query_body = '\n'.join(range_initializers) + '\n' + query_body
    yaml_lines.append("body: |-")
    for line in query_body.split('\n'):
        yaml_lines.append(f"  {line}")
    
    return '\n'.join(yaml_lines)

def camel_to_snake(name):
    # Handle acronyms like HTTP, CSV, API, etc. by converting them to Http, Csv, Api
    acronym_pattern = re.compile(r'([A-Z])([A-Z]+)')
    name = acronym_pattern.sub(lambda m: m.group(1) + m.group(2).lower(), name)
    
    # Remove existing underscores if they exist
    name = name.replace('_', '')

    # Insert underscores between camelCase boundaries
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
        if not content.endswith('\n'):
            f.write('\n')  # Ensure the file ends with a newline

def extract(
        dashboard_file_path, 
        output_folder='extracted',
        function_folder='extracted',
        create_yaml=False,
        create_functions=False,
        create_queries=False
        ):
    """
    Extract Kusto queries from Azure Data Explorer dashboard export file.
    
    Args:
        dashboard_file_path: Path to the dashboard JSON file
        output_folder: Folder to save extracted queries in
        function_folder: Folder name to use in the function docstring and creation command
        yaml_only: Whether to only emit YAML files (no KQL or raw queries)
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
    
    for param in dashboard.get('parameters', []):
        if 'variableName' in param:
            parameters_by_name[param['variableName']] = param
        
    # Generate new names for base queries
    snake_names = {}
    for bq_name, bq in base_queries_by_name.items():
        # replace prefixes 
        name_without_prefix = bq_name.replace('BQ', function_folder.lower())

        # convert to snake_case
        snake_names[bq_name] = camel_to_snake(name_without_prefix)

    # Keep track of what we've processed
    processed_count = 0

    # Extract each base query
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

        # Build a version of the query text where base queries are replaced with function calls
        query_text = query.get('text', '')
        query_text_with_functions = str(query_text)
        for function_name in query.get('usedVariables', []):
            if function_name not in base_queries_by_name:
                continue
            bq = base_queries_by_name[function_name]
            bq_query_id = bq.get('queryId')
            if not bq_query_id:
                continue

            # Replace variable with function call using snake_case name
            snake_case_func_name = snake_names.get(function_name, function_name)
            sig = function_signature(snake_case_func_name, parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, bq_query_id))
            query_text_with_functions = query_text_with_functions.replace(function_name, sig)

        # Get query name from variable name
        bq_name = base_query.get('variableName', f'unknown_{base_query_id}')
        # Use the snake_case name if available
        function_name = snake_names.get(bq_name, bq_name)
        timestamp = datetime.now().strftime('%Y-%m-%d')  # Only to the hour
        docstring=f"{bq_name} exported from dashboard {dashboard_title} on {timestamp}"
        query_parameters = parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, query_id)

        # generate the output contents
        if create_functions:
            final_text = generate_kusto_function(
                function_name=function_name,
                query_text=query_text_with_functions,
                query_parameters=query_parameters,
                docstring=docstring,
                function_folder=function_folder
            )
            save(output_path / f"create_{function_name}.kql", final_text)
        if create_yaml:
            final_text = generate_yaml_function(
                function_name=function_name,
                query_text=query_text_with_functions,
                query_parameters=query_parameters,
                docstring=docstring,
                function_folder=function_folder
            )
            save(output_path / f"{function_name}.yml", final_text)
        if create_queries:
            final_text = generate_kusto_query(
                bq_name=function_name,
                query_text=query_text,
                query_parameters=query_parameters
            )
            save(output_path / f"{function_name}.kusto", final_text)

        processed_count += 1
    print(f"Extracted {processed_count} base queries from dashboard '{dashboard_file_path}' into '{output_folder}'")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Extract Kusto queries from Azure Data Explorer dashboard export")
    parser.add_argument("dashboard_file", help="Path to the dashboard JSON file")
    parser.add_argument("--output", "-o", default="extracted", help="Where to save output files")
    parser.add_argument("--function_folder", "-ff", default="extracted", help="Where to create functions in the kusto database's /functions dir")
    parser.add_argument("--yaml", action="store_true", help="Emit YAML files")
    parser.add_argument("--functions", action="store_true", help="Emit create-or-alter function definition files")
    parser.add_argument("--queries", action="store_true", help="Emit ADE-style basequery amalgams")
    args = parser.parse_args()

    extract(
        args.dashboard_file, 
        args.output,
        args.function_folder,
        create_yaml=args.yaml,
        create_functions=args.functions,
        create_queries=args.queries
    )