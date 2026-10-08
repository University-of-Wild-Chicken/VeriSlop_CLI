import re

def solve(data):
    text = data.get("text", "")
    lines = text.split("\n")
    n = len(lines)
    results = []
    i = 0
    while i < n:
        line = lines[i]
        m = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if m:
            marker = m.group(1)[0]
            opener_len = len(m.group(1))
            info_raw = m.group(2)
            if marker == '`' and '`' in info_raw:
                i += 1
                continue
            info = info_raw.strip()
            start = i
            j = i + 1
            body = []
            closed = False
            end = None
            while j < n:
                cl = lines[j]
                cm = re.match(r'^ {0,3}(' + re.escape(marker) + '{' + str(opener_len) + ',})[ \t]*$', cl)
                if cm:
                    closed = True
                    end = j
                    break
                body.append(cl)
                j += 1
            results.append({
                "info": info,
                "start": start,
                "end": end,
                "text": "\n".join(body),
                "closed": closed
            })
            i = j + 1 if closed else n
        else:
            i += 1
    return results
