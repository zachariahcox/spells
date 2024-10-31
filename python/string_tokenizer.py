'''
parse string into tokens
'''

def parse_orchestrationid(oid):
    '''
    Parse an orchestration id into component parts.
    '''
    tokens = oid.split('.')
    count = len(tokens)

    # the attempt number is the only component of orchestration
    #   which can be (or begin with) an integer.
    attempt_number = 0
    for t in tokens:
        if t.isdigit():
            attempt_number = int(t)

    return {
        'planid':     tokens[0] if count > 1 else None,
        'stage':      tokens[1] if count > 2 else None,
        'jobFactory': tokens[2] if count > 3 else None,
        'job':        tokens[3] if count > 4 else None,
        'attempt':    attempt_number,
        'checkpoint': count > 1 and tokens[-1].lower() == 'checkpoint'
    }

if __name__ == "__main__":
    d = parse_orchestrationid('f4ce3766-f6cb-4106-bda1-7cacead4af30.stage_6a9e65ddcdfe469c8fdfff62b73ff99a_3_3.phase_1.__default.3.checkpoint')
    print(d)
