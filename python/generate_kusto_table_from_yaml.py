"""
Generate kusto table from employee data
Such as: https://github.com/github/thehub/blob/main/docs/_data/hubbers.yml
@zachariahcox
"""
import os
import sys
import yaml

def load_org_chart(d):
    # load manager to employee map
    manager_to_employees = {}
    employee_to_manager = {}

    for meta in d.values():
        user = meta['github_login']
        manager = meta['manager'] # managers are logins, not emails.
        if user == manager:
            continue # not allowed to report to yourself (though this shows up in the data sometimes).

        # we know the manager
        employee_to_manager[user] = manager

        # find the employees
        employees = manager_to_employees.get(manager)
        if not employees:
            manager_to_employees[manager] = employees = set()
        employees.add(user)

    return manager_to_employees, employee_to_manager

def org_size_count(h, include_managers=True):
    counts = {}

    def sub_org_size(m):
        count = counts.get(m)
        if count is None:
            count = 0
            employees = h.get(m)
            if employees:
                for e in employees:
                    count += sub_org_size(e)
                    if include_managers or e not in h:
                        count += 1
            counts[m] = count
        return count

    for m in h.keys():
        counts[m] = sub_org_size(m)

    return counts

def reporting_chain(manager_to_employees, employee_to_manager):
    chains = {}
    for m in manager_to_employees.keys():
        chain = []
        current_manager = m
        while True:
            next_manager = employee_to_manager.get(current_manager)
            if not next_manager or next_manager == current_manager:
                break
            chain.append(next_manager)
            current_manager = next_manager
        chains[m] = chain
    return chains

if __name__ == "__main__":
    assert len(sys.argv) == 2, 'please provide the path to a data file.'
    f = sys.argv[1]
    assert os.path.isfile(f), f + " is not a file."

    with open(f, 'r', encoding="utf8") as src:
        try:
            data = yaml.safe_load(src)
        except yaml.YAMLError as exc:
            print(exc)

    manager_to_employees, employee_to_manager = load_org_chart(data)
    chain = reporting_chain(manager_to_employees, employee_to_manager)
    org_counts = org_size_count(manager_to_employees)
    ic_counts = org_size_count(manager_to_employees, include_managers=False)
    output_file = os.path.join(os.path.dirname(f), "output.kql")

    # clean up
    if os.path.exists(output_file):
        os.remove(output_file)

    # file generation
    with open(output_file, 'w') as out:
        out.write("datatable(manager:string, reporting_chain:string, reports_direct:long, reports_all:long, reports_ic:long)[\n")
        for m in sorted(manager_to_employees.keys()):
            row_values = [
                '"' + m + '"',
                '"' + ",".join(chain[m]) + '"', # in kusto convert into array by split(column, ",")
                len(manager_to_employees[m]),
                org_counts[m],
                ic_counts[m]
                ]
            out.write(", ".join(str(e) for e in row_values) + ",\n")
        out.write("]\n")
