"""
Extract Kusto Queries from Azure Data Explorer Dashboard Files
==============================================================

This script extracts Kusto queries from an Azure Data Explorer dashboard export file
and converts them into reusable KQL functions, raw queries, or YAML definitions.

Dashboard exports follow the schema: https://dataexplorer.azure.com/static/d/schema/60/dashboard.json

Features:
---------
- Extracts all base queries from dashboards
- Automatically detects query parameters and their dependencies
- Generates proper function signatures with correct parameter types
- Supports both KQL function format and YAML format (for use with https://github.com/github/KustoSchemaTools)
- Preserves query dependencies and structure
- Automatic conversion of camelCase names to snake_case
- Special handling for time range parameters (_startTime, _endTime)

Usage:
------
```
python extract_base_queries.py [options] dashboard_file.json

Options:
  -h, --help                      Show this help message and exit
  --output OUTPUT, -o OUTPUT      Output directory for extracted queries (default: 'extracted')
  --output_database <database>, -fs <database>  Functions will be created in this database schema (default: 'extracted')
  --output_function_folder FOLDER, -ff FOLDER  Folder name to use within Kusto (default: 'extracted')
  --yaml                          Generate YAML files for KustoSchemaTools
  --functions                     Generate regular Kql function declarations (create-or-alter)
  --queries                       Generate .kql files with raw queries
  --cluster_databases_folder FOLDER, -cs FOLDER  Path to KustoSchemaTools folder containing folders for each database definition
```

Examples:
---------
# Basic extraction to default folder (no output files created unless you specify options):
python extract_base_queries.py dashboard.json

# Extract to specific folder with all output types:
python extract_base_queries.py --output queries --yaml --functions --queries dashboard.json

# Generate only YAML files with custom function folder:
python extract_base_queries.py --output_function_folder "team/dashboard/awesome" --output_database "mydb" --cluster_databases_folder path/to/KustoSchemaTools/root/ --yaml dashboard.json

"""
import json
import os
import re
from typing import Dict, Set, List
from datetime import datetime

class Parameter(object):
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

    def __init__(self, 
        name: str, 
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
    
    def default_value_initializer(self):
        """
        Format the default value for use in KQL or YAML.
        Ensures string values are properly quoted only when needed.
        
        Returns:
            - For non-scalar types: always returns dynamic(null)
            - For string scalar types: returns quoted string if not already quoted
            - For other scalar types: returns the value as is
        """
        if self.selection_type != 'scalar':
            return "dynamic(null)"
            
        value = self.default_value
        
        # Only quote string values if they're scalar and not already quoted
        if self.kind == 'string' and value and not (value.startswith('"') and value.endswith('"')):
            return f'"{value}"'
        
        return value

    @property
    def default_value(self) -> str:
        if self._default_value:
            return self._default_value

        if self.selection_type != 'scalar':
            return "dynamic(null)" # return dynamic(null) for any list
        
        self._default_value = Parameter.KUSTO_DEFAULT_VALUES.get(self.kind, 'dynamic(null)')
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
            value = self.default_value_initializer()
            i = f"let {self.name} = {value};"
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
    result = []
    for p in parameters:
        value = p.default_value_initializer()
        result.append(f"{p.name}:{p.kind_with_selection()}={value}")
    return result

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

def update_schema_references(
        database_name: str,
        functions: List[str], 
        query_text: str
    ) -> str:
    modified_lines = []
    file_modified = False
    discovered_let_statements = []
    lines = query_text.splitlines()
    for line_number, line in enumerate(lines):
        modified_line = line
        for function in functions:
            # If we have already discovered this function in a let statement,
            # skip further processing for this function
            if function in discovered_let_statements:
                continue

            prefix = f"database('{database_name}')"
            qualified_function = f"{prefix}.{function}"
            
            # Skip if the qualified version already exists in this line
            if qualified_function in modified_line:
                continue
            
            # Find all occurrences of the function name
            index = 0
            while index < len(modified_line):
                index = modified_line.find(function, index)
                if index == -1:
                    break
                    
                # Check if this function name might already be qualified
                replace = True
                decision = False
                rev_line_number = line_number
                rev_line = lines[rev_line_number]
                rev_index = index # use this index initially
                while not decision and rev_line_number >= 0:
                    for i in range(rev_index - 1, - 1, -1):
                        c = rev_line[i]
                        if c.isspace(): 
                            continue

                        # check for `let` statement
                        if c == 't' and i >= 3 and rev_line[i-2:i+1] == 'let':
                            replace = False # this is a let statement, do not replace
                            decision = True
                            discovered_let_statements.append(function)
                            break

                        replace = c != '.' # this is the only allowable character
                        decision = True
                        break
                    rev_line_number -= 1
                    rev_line = lines[rev_line_number]
                    rev_index = len(rev_line) - 1

                if replace:
                    # Replace this occurrence with the qualified version
                    modified_line = modified_line[:index] + qualified_function + modified_line[index + len(function):]
                    file_modified = True
                    # Skip ahead to avoid infinite loop
                    index += len(qualified_function)
                else:
                    # If we found a non-whitespace character before the function name, skip this occurrence
                    index += len(function)

                # If we found a let statement, no need to check further for this function in this line
                if function in discovered_let_statements:
                    break

        # Append the modified line to the list 
        modified_lines.append(modified_line)
    
    # Only write back if changes were made
    if file_modified:
        return "\n".join(modified_lines)
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
    # Create parent directory if it doesn't exist
    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
        if not content.endswith('\n'):
            f.write('\n')  # Ensure the file ends with a newline

def extract(
    dashboard_file_path: str,
    output_folder: str = 'extracted',
    output_database_name: str = 'extracted',
    output_function_folder: str = 'extracted',
    create_yaml: bool = False,
    create_functions: bool = False,
    create_queries: bool = False,
    cluster_databases_folder: str = str()
) -> None:
    """
    Extract Kusto queries from Azure Data Explorer dashboard export file.
    
    Args:
        dashboard_file_path: Path to the dashboard JSON file
        output_folder: Folder to save extracted queries in
        output_database_name: Schema name to use for function references in generated code
        output_function_folder: Folder name to use in the function docstring and creation command
        create_yaml: Whether to generate YAML files for KustoSchemaTools
        create_functions: Whether to generate .kql files with function declarations
        create_queries: Whether to generate .kql files with raw queries
        cluster_databases_folder: Path to folder containing cluster schema files for resolving references
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
        name_without_prefix = bq_name.replace('BQ', output_function_folder.lower())
        snake_name = camel_to_snake(name_without_prefix)
        output_function_names[bq_name] = snake_name

    # Load all datasources and functions currently in cluster
    function_names_by_database = dict[str, List[str]]()
    if cluster_databases_folder:
        for root, _, files in os.walk(cluster_databases_folder):
            if os.path.basename(root) != "functions": 
                continue
            database_name = os.path.basename(os.path.dirname(root))
            database_functions = function_names_by_database.setdefault(database_name, [])
            for file in files:
                if file.endswith('.yml'):
                    function_name = os.path.splitext(file)[0]
                    database_functions.append(function_name)

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

        # In which database was this query defined?
        database_name = datasources_by_id.get(datasource_id, {}).get('database')
        if not database_name:
            print(f"Warning: No database name found for datasource ID {datasource_id}")
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
            fully_qualified_name = f"database('{output_database_name}').{sig}"
            query_text_modified = query_text_modified.replace(referenced_base_query_name, fully_qualified_name)

        # Deal with parameters
        query_parameters = parameters_for_query(base_queries_by_name, parameters_by_name, queries_by_id, query_id)
        query_text_modified = replace_initialized_parameters(query_text_modified, query_parameters)

        # Reference schemas explicitly 
        if function_names_by_database:
            # load the functions in the original database for this query
            functions = function_names_by_database.get(database_name)
            if functions:
                query_text_modified = update_schema_references(
                    database_name=database_name,
                    functions=functions,
                    query_text=query_text_modified)
                    

        # Generate docstring and function name
        bq_name = base_query.get('variableName', f'unknown_{base_query_id}')
        function_name = output_function_names.get(bq_name, bq_name)
        docstring=f"{bq_name} exported from dashboard {dashboard_title} using extract_base_queries.py"

        # Generate the output contents
        # Create output folder if it doesn't exist
        if create_functions or create_yaml or create_queries:
            os.makedirs(output_folder, exist_ok=True)

        if create_functions:
            final_text = generate_kusto_function(
                function_name=function_name,
                query_text=query_text_modified,
                query_parameters=query_parameters,
                docstring=docstring,
                function_folder=output_function_folder
            )
            save(os.path.join(output_folder, f"create_{function_name}.kql"), final_text)

        if create_yaml:
            final_text = generate_yaml_function(
                function_name=function_name,
                query_text=query_text_modified,
                query_parameters=query_parameters,
                docstring=docstring,
                function_folder=output_function_folder
            )
            save(os.path.join(output_folder, f"{function_name}.yml"), final_text)

        if create_queries:
            final_text = generate_kusto_query(
                bq_name=function_name,
                query_text=query_text, # do not use modified version
                query_parameters=query_parameters
            )
            save(os.path.join(output_folder, f"{function_name}.kusto"), final_text)

        processed_count += 1
    print(f"Extracted {processed_count} base queries from dashboard '{dashboard_file_path}' into '{output_folder}'")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Extract Kusto queries from Azure Data Explorer dashboard export")
    parser.add_argument("dashboard_file", help="Path to the dashboard JSON file")
    parser.add_argument("--output", "-o", default="extracted", help="Where to save output files")
    parser.add_argument("--output_database", "-fs", default="extracted", help="Which database will contain these functions?")
    parser.add_argument("--output_function_folder", "-ff", default="extracted", help="Where should Kusto display these functions?")
    parser.add_argument("--yaml", action="store_true", help="Emit YAML files")
    parser.add_argument("--functions", action="store_true", help="Emit create-or-alter function definition files")
    parser.add_argument("--queries", action="store_true", help="Emit ADE-style basequery amalgams")
    parser.add_argument("--cluster_databases_folder", "-cs", help="Directory containing definition files for all databases in the cluster")
    args = parser.parse_args()

    extract(
        args.dashboard_file, 
        args.output,
        args.output_database,
        args.output_function_folder,
        create_yaml=args.yaml,
        create_functions=args.functions,
        create_queries=args.queries,
        cluster_databases_folder=args.cluster_databases_folder
    )