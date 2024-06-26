"""
Generate kusto table from employee data
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

def save_kusto_datatable(
        filename, 
        org_chart, 
        employee_to_manager,
        org_counts, 
        ic_counts
    ):
    # clean up
    if os.path.exists(filename):
        os.remove(filename)

    # file generation
    with open(filename, 'w') as out:
        out.write("datatable(m3:string, director:string, reports_direct:long, reports_all:long, reports_ic:long)[\n")
        for m in sorted(org_chart.keys()):
            row_values = [
                '"' + employee_to_manager.get(m, "") + '"', 
                '"' + m + '"', 
                len(org_chart[m]), 
                org_counts[m], 
                ic_counts[m]
                ]
            out.write(", ".join(str(e) for e in row_values) + ",\n")
        out.write("]\n")

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
    c = org_size_count(manager_to_employees)
    ic = org_size_count(manager_to_employees, include_managers=False)
    output_file = os.path.join(os.path.dirname(f), "output.kql")

    save_kusto_datatable(output_file, manager_to_employees, employee_to_manager, c, ic)
