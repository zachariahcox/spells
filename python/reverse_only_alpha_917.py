
def reverseOnlyLetters(s: str) -> str:
    i = 0
    j = len(s) - 1

    # o = []
    # for c in s:
    #     if c.isalpha():
    #         # insert the next alpha character from the end
    #         while j >= 0 and not s[j].isalpha():
    #             j -= 1 # leave the non-alpha characters alone
    #         o.append(s[j])
    #         j -= 1
    #     else:
    #         o.append(c) # add the non-alpha character

    # classic two pointer solution
    o = [c for c in s] # make a copy output buffer
    while i <= j:
        # find next i from beginning
        ci = s[i]
        while not ci.isalpha() and i < j:
            o[i] = ci
            i += 1
            ci = s[i]

        # find next j from end
        cj = s[j]
        while not cj.isalpha() and j > i:
            o[j] = cj
            j -= 1
            cj = s[j]

        # swap and increment
        o[i] = cj
        o[j] = ci
        i += 1
        j -= 1

    return "".join(o)


for i, o in [
    {"ab-cd", "dc-ba"},
    {"a-bC-dEf-ghIj", "j-Ih-gfE-dCba"},
    {"Test1ng-Leet=code-Q!", "Qedo1ct-eeLg=ntse-T!"}
    ]:
    a = reverseOnlyLetters(i)
    print("expected: ", o, "\n", " actual: ", a)