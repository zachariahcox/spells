

def collect_data(elements):
    data_collector = {}
    for key, value in elements:
        metadata = data_collector.get(key)
        if not metadata:
            # hydrate
            data_collector[key] = metadata = {}

        # instances of key
        count = metadata.get("count", 0)
        metadata["count"] = count + 1

        # sum of value
        sum = metadata.get("sum", 0)
        metadata["sum"] = sum + value
    return data_collector

d = collect_data((
    ("a", 1),
    ("b", 2),
    ("b", 3),
    ("c", 1),
    ))

for k, v in d.items():
    print (k, v)