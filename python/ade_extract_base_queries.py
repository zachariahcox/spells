import json
import os
import re
import sys
from collections import deque
from pathlib import Path
from typing import Dict, Any, List, Set


def get_kusto_default_for_type(param_type: str) -> str:
    """
    Return an appropriate default value for a Kusto parameter based on its type.
    
    Args:
        param_type: The type of parameter (from the 'kind' field)
        
    Returns:
        A string representation of a default value in Kusto syntax
    """
    param_type = param_type.lower()
    if param_type == 'string':
        return '""'  # Empty string
    elif param_type in ['long', 'int']:
        return '0'  # Integer zero
    elif param_type == 'double':
        return '0.0'  # Float zero
    elif param_type == 'boolean':
        return 'false'  # Boolean false
    elif param_type == 'datetime':
        return 'datetime(null)'  # Null datetime
    elif param_type == 'timespan':
        return 'timespan(0)'  # Zero timespan
    elif param_type == 'dynamic':
        return 'dynamic({})'  # Empty dynamic object
    else:
        return 'dynamic(null)'  # Default fallback


# This will hold the dependencies between queries and their used variables
QUERY_PARAMETERS: Dict[str, Set[str]] = {}

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

def extract_kusto_queries(
        dashboard_file_path, 
        output_folder='kusto_queries_output'
        ):
    """
    Extract Kusto queries from Azure Data Explorer dashboard export file.
    
    Args:
        dashboard_file_path: Path to the dashboard JSON file
        output_folder: Folder to save extracted queries in
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
    print(f"Processing {len(base_queries_by_id)} base queries...")
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
        datasource_folder = output_path / datasource_name
        datasource_folder.mkdir(exist_ok=True)
        
        # get full list of variables used in this query
        query_parameters = get_used_parameters(base_queries_by_name, queries_by_id, query_id)

        # Get the query text and used variables
        query_text = query.get('text', '')

        # Initialize parameter variables if they exist
        parameter_initializations = []
        for p in sorted(query_parameters):
            if p in parameters_by_name:
                param = parameters_by_name[p]
                param_type = param.get('kind', 'string')
            elif p in ("_startTime", "_endTime"):
                # Special handling for time parameters
                param_type = 'datetime'
            else:
                continue
            # Get the default value for this parameter type
            default_value = get_kusto_default_for_type(param_type)
            parameter_initializations.append(f"let {p} = {default_value};")

        # Build final content
        bq_name = base_query.get('variableName', f'unknown_{base_query_id}')
        final_text = f"// {datasource_name} / {bq_name}\n//\n"
        if parameter_initializations:
            final_text += "\n".join(parameter_initializations) + "\n"
        final_text += "//\n" + query_text
        
        # Write the final query to the file overwriting any existing content
        file_path = datasource_folder / f"{bq_name}.kql"
        with open(file_path, 'w') as f:
            f.write(final_text)
        
        processed_count += 1
        
    print(f"Processed {processed_count} queries. Output saved to '{output_folder}'")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: python {__file__} <path/to/json> [path/to/output/folder]")
        sys.exit(1)
    
    dashboard_file = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else 'kusto_queries_output'
    extract_kusto_queries(dashboard_file, output_folder)
