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

class Parameter(object):
    def __init__(self, name: str, 
                 kind: str, 
                 selection_type: str,
                 default_value: str = "",
                 initializer: str = "",
                 initialized_name: str = ""
                 ):
        self.name = name
        self.kind = kind
        self.selection_type = selection_type
        self.default_value = default_value
        self.initializer = initializer
        self.initialized_name = initialized_name

    @property
    def default_value(self) -> str:
        if self._default_value:
            return self._default_value

        if self.selection_type != 'scalar':
            return "dynamic(null)" # return dynamic(null) for any list
        
        KUSTO_DEFAULT_VALUES = {
            'string': '""',               # Empty string
            'long': 'long(0)',            # Integer zero
            'int': 'int(0)',              # Integer zero
            'real': 'real(0.0)',          # Real zero
            'double': 'double(0.0)',      # Float zero
            'boolean': 'false',           # Boolean false
            'datetime': 'datetime(null)', # Null datetime
            'timespan': 'timespan(0)',    # Zero timespan
            'dynamic': 'dynamic(null)'    # Empty dynamic object
        }

        self._default_value = KUSTO_DEFAULT_VALUES.get(self.kind, 'dynamic(null)')
        return self._default_value

    @default_value.setter
    def default_value(self, value: str):
        self._default_value = value
  
    def kind_with_selection(self) -> str:
        if self.selection_type == 'scalar':
            return self.kind
        return 'dynamic'  # For lists, we use dynamic type

    @property
    def initializer(self) -> str:
        """
        Returns a Kusto initializer for this parameter.
        This is used in the function body to set default values.
        """
        if self._initializer:
            return self._initializer
        
        # build a default initializer
        if self.selection_type == 'scalar':
            i = f"let {self.name} = {self.default_value};"
        else:
            i = f"let {self.name} = dynamic({self.default_value});"

        self._initializer = i
        return i
    
    @initializer.setter
    def initializer(self, value: str):
        self._initializer = value

    @property
    def initialized_name(self) -> str:
        if self._initialized_name:
            return self._initialized_name
        return ""
    @initialized_name.setter
    def initialized_name(self, value: str):
        self._initialized_name = value

# Cache for used parameters to avoid redundant calculations
QUERY_PARAMETERS: Dict[str, Set[str]] = {}

RESERVED_PARAMETERS = {
    '_startTime': ('_startTimeInitialized', "let _startTimeInitialized = coalesce(_startTime, startofday(ago(7d)));"),
    '_endTime': ('_endTimeInitialized', "let _endTimeInitialized = coalesce(_endTime, endofday(now()));"),
}

def parameters_for_query(
    base_queries_by_name, 
    parameters_by_name,
    queries_by_id,
    query_id
) -> list[Parameter]:
    """
    What parameters are needed to power this query?
    
    This function analyzes a query and its dependencies to determine which parameters are used.
    It returns a list of tuples containing the parameter name, type, and selection type.
    
    The parameters are sorted such that '_startTime' and '_endTime' appear first, followed by other parameters.
    
    Args:
        base_queries_by_name: Dictionary mapping variable names to base queries
        parameters_by_name: Dictionary mapping parameter names to parameter objects
        queries_by_id: Dictionary mapping query IDs to query objects
        query_id: ID of the query to analyze
        
    Returns:
        List of tuples (parameter_name, parameter_type, selection_type)
    """
    def get_referenced_parameters(
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
        for p in ('_startTime', '_endTime'):
            if p in text:
                parameters.add(p)
        
        # Process each used variable
        for var in query.get('usedVariables', []):
            if var in base_queries_by_name:
                bq = base_queries_by_name[var]
                bq_query_id = bq.get('queryId')
                if not bq_query_id:
                    continue
                parameters.update(get_referenced_parameters(
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

    result= []
    names = get_referenced_parameters(base_queries_by_name, queries_by_id, query_id)
    for p, (initialized_name, initializer) in RESERVED_PARAMETERS.items():
        if p in names:
            param = Parameter(p, 'datetime', "scalar", 
                        initializer=initializer, 
                        initialized_name=initialized_name)
            result.append(param)

    # Collect other parameters, force stable order
    for p in sorted(names):
        if p in RESERVED_PARAMETERS.keys():
            continue
        param = Parameter(p, 
            kind=parameters_by_name[p]["kind"].lower(), 
            selection_type=parameters_by_name[p]["selectionType"].lower(),
            default_value=parameters_by_name[p].get("defaultValue", {}).get('value', ''),
            )
        result.append(param)
    return result

def function_call_signature(
    function_name: str, 
    parameters: list[Parameter]
) -> str:
    return f"{function_name}({', '.join(param.name for param in parameters)})"

def function_definition_parameters(
    parameters: list[Parameter]
) -> list[str]:
    return [f"{p.name}:{p.kind_with_selection()}={p.default_value}"
            for p in parameters]

def get_parameter_initializers(
    query_parameters: list[Parameter]
) -> list[str]:
    return [p.initializer for p in query_parameters if p.initialized_name]

def replace_initialized_parameters(
        query_text: str, 
        parameters: list[Parameter]
        ) -> str:
    for p in parameters:
        if p.initialized_name:
            query_text = query_text.replace(p.name, p.initialized_name)
    return query_text

def generate_kusto_function(
    function_name: str,
    query_text: str,
    query_parameters: list[Parameter],
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
    parameter_initializers = []
    if query_parameters:
        separator = f',\n{4 * " "}'
        params = function_definition_parameters(query_parameters)
        function_parameters += separator + separator.join(params) + "\n"
        parameter_initializers = get_parameter_initializers(query_parameters)

    # build function body
    lines.append(f"{function_name}({function_parameters}){{")
    if parameter_initializers:
        lines.append("\n".join(parameter_initializers))
    lines.append(query_text)
    lines.append(f"}}")

    return '\n'.join(lines)

def generate_kusto_query(
    bq_name: str,
    query_text: str,
    query_parameters: list[Parameter]
) -> str:
    # Build query with components
    query_lines = []

    # Add parameter initializations if they exist
    if query_parameters:
        # Create let statements for parameters
        query_lines.append(f"// Parameters -- begin")
        query_lines.extend([p.initializer for p in query_parameters])
        query_lines.append(f"// Parameters -- end")
        query_lines.append("//")  # Empty line for separation
        
    query_lines.append(f"// {bq_name} -- begin")
    query_lines.append(query_text)
    query_lines.append(f"// {bq_name} -- end")
    return '\n'.join(query_lines)

def generate_yaml_function(
    function_name: str,
    query_text: str,
    query_parameters: list[Parameter],
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
        params = ','.join(function_definition_parameters(query_parameters))
        yaml_lines.append(f"parameters: {params}")
    
    # Format the query body to maintain proper indentation
    yaml_lines.append("body: |-")
    for line in get_parameter_initializers(query_parameters) + query_text.strip().split('\n'):
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
    dashboard_file_path: str,
    output_folder: str = 'extracted',
    function_schema: str = 'extracted',
    function_folder: str = 'extracted',
    create_yaml: bool = False,
    create_functions: bool = False,
    create_queries: bool = False
) -> None:
    """
    Extract Kusto queries from Azure Data Explorer dashboard export file.
    
    Args:
        dashboard_file_path: Path to the dashboard JSON file
        output_folder: Folder to save extracted queries in
        function_schema: Schema to use for the functions
        function_folder: Folder name to use in the function docstring and creation command
        yaml_only: Whether to only emit YAML files (no KQL or raw queries)
    """
    print(f"Loading dashboard file: {dashboard_file_path}")
    with open(dashboard_file_path, 'r') as f:
        dashboard = json.load(f)

    dashboard_title = dashboard.get('title', 'Unknown Dashboard')

    # Create lookup dictionaries for quick access
    base_queries_by_id = {}
    base_queries_by_query_id = {}
    base_queries_by_name = {}
    queries_by_id = {}
    datasources_by_id = {}
    parameters_by_name = {}
    
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
    output_function_names = {}
    for bq_name, _ in base_queries_by_name.items():
        name_without_prefix = bq_name.replace('BQ', function_folder.lower())
        snake_name = camel_to_snake(name_without_prefix)
        output_function_names[bq_name] = snake_name

    # Keep track of what we've processed
    processed_count = 0

    # Extract each base query
    for base_query_id, base_query in base_queries_by_id.items():
        query_id = base_query.get('queryId')
        if not query_id or query_id not in queries_by_id:
            print(f"Warning: No matching query found for base query ID {base_query_id}")
            continue

        # Load datasource ("schema") information
        query = queries_by_id[query_id]
        datasource_info = query.get('dataSource', {})
        datasource_id = datasource_info.get('dataSourceId')
        
        if not datasource_id or datasource_id not in datasources_by_id:
            print(f"Warning: No data source found for query ID {query_id}")
            continue

        # In ADE dashboards, base queries are defined inline and capture parameters from their parent scope.
        # Build a version of the query text where base queries are replaced with function calls to avoid this requirement.
        query_text = query.get('text', '')
        query_text_modified = str(query_text)
        for referenced_base_query_name in query.get('usedVariables', []):
            if referenced_base_query_name not in base_queries_by_name:
                continue
            referenced_bq = base_queries_by_name[referenced_base_query_name]
            referenced_bq_query_id = referenced_bq.get('queryId')
            if not referenced_bq_query_id:
                continue

            # Replace variable with function call using snake_case name
            sig = function_call_signature(
                function_name=output_function_names.get(referenced_base_query_name, referenced_base_query_name), 
                parameters=parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, referenced_bq_query_id)
                )
            fully_qualified_name = f"database('{function_schema}').{sig}"
            query_text_modified = query_text_modified.replace(referenced_base_query_name, fully_qualified_name)

        # Deal with parameters
        query_parameters = parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, query_id)
        query_text_modified = replace_initialized_parameters(query_text_modified, query_parameters)

        # Generate docstring and function name
        bq_name = base_query.get('variableName', f'unknown_{base_query_id}')
        function_name = output_function_names.get(bq_name, bq_name)
        docstring=f"{bq_name} exported from dashboard {dashboard_title} on {datetime.now().strftime('%Y-%m-%d')}"

        # Generate the output contents
        # Create output folder if it doesn't exist
        output_path = Path(output_folder)
        if create_functions or create_yaml or create_queries:
            output_path.mkdir(exist_ok=True)

        if create_functions:
            final_text = generate_kusto_function(
                function_name=function_name,
                query_text=query_text_modified,
                query_parameters=query_parameters,
                docstring=docstring,
                function_folder=function_folder
            )
            save(output_path / f"create_{function_name}.kql", final_text)

        if create_yaml:
            final_text = generate_yaml_function(
                function_name=function_name,
                query_text=query_text_modified,
                query_parameters=query_parameters,
                docstring=docstring,
                function_folder=function_folder
            )
            save(output_path / f"{function_name}.yml", final_text)

        if create_queries:
            final_text = generate_kusto_query(
                bq_name=function_name,
                query_text=query_text, # do not use modified version
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
    parser.add_argument("--function_schema", "-fs", default="extracted", help="Which schema will contain these functions?")
    parser.add_argument("--function_folder", "-ff", default="extracted", help="Where to create functions in the kusto database's /functions dir")
    parser.add_argument("--yaml", action="store_true", help="Emit YAML files")
    parser.add_argument("--functions", action="store_true", help="Emit create-or-alter function definition files")
    parser.add_argument("--queries", action="store_true", help="Emit ADE-style basequery amalgams")
    args = parser.parse_args()

    extract(
        args.dashboard_file, 
        args.output,
        args.function_schema,
        args.function_folder,
        create_yaml=args.yaml,
        create_functions=args.functions,
        create_queries=args.queries
    )