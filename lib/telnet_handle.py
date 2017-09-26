import telnetlib

HOST = "192.168.163.2"
user = "ionos"
password = "!0n0s@123"

handle = None

def lcs(S,T):
    m = len(S)
    n = len(T)
    counter = [[0]*(n+1) for x in range(m+1)]
    longest = 0
    lcs_set = set()
    for i in range(m):
        for j in range(n):
            if S[i] == T[j]:
                c = counter[i][j] + 1
                counter[i+1][j+1] = c
                if c > longest:
                    lcs_set = set()
                    longest = c
                    lcs_set.add(S[i-c+1:i+1])
                elif c == longest:
                    lcs_set.add(S[i-c+1:i+1])

    return lcs_set


def connect(ipAddress, username, password):
    global handle
    tn = telnetlib.Telnet(ipAddress)

    tn.read_until("login: ")
    tn.write(username + "\n")
    if password:
        tn.read_until("Password: ")
        tn.write(password + "\n")

    handle = tn


def find_prompt():
    global handle
    handle.write("\n")
    output = handle.read_until("came$#*from#$*mars", 1)
    prompt1 = ""
    if output:
        prompt1 = output.splitlines()[-1]

    handle.write("\n")
    output = handle.read_until("came$#*from#$*mars", 1)
    prompt2 = ""
    if output:
        prompt2 = output.splitlines()[-1]

    print prompt1, prompt2
    print lcs(prompt1, prompt2)

connect(HOST, user, password)
find_prompt()

