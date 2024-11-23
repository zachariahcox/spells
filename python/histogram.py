'''
aggregate example
'''
def aggregate(elements):
    '''
    collect stats for histogram-like use cases
    '''
    data_collector = {}
    for key, value in elements:
        # load state or hydrate
        metadata = data_collector.get(key)
        if not metadata:
            data_collector[key] = metadata = {}

        # instances of key
        count = metadata.get("count", 0)
        metadata["count"] = count + 1

        # sum of value
        sum = metadata.get("sum", 0)
        metadata["sum"] = sum + value

        # min of value
        min = metadata.get("min", value)
        metadata["min"] = value if value < min else min

        # max of value
        max = metadata.get("max", value)
        metadata["max"] = value if value > max else max

    return data_collector

d = aggregate((
    ("a", 1),
    ("b", 2),
    ("b", 3),
    ("c", 1),
    ))

for k, v in d.items():
    print (k, v)