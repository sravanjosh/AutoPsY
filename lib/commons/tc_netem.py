__author__ = 'joshisk'


def generate_tc_cmd(interface, operation,
                 packet_limit=None, delay_time=None, delay_jitter=None, delay_correlation=None,
                 corrupt_percent=None, corrupt_correlation=None,
                 duplicate_percent=None, duplicate_correlation=None,
                 loss_percent=None, loss_correlation=None,
                 delay_distribution=None,
                 reorder_percent=None, reorder_correlation=None, reorder_gap=None
                 ):
    """
    Usage: ... netem [ limit PACKETS ]
                 [ delay TIME [ JITTER [CORRELATION]]]
                 [ distribution {uniform|normal|pareto|paretonormal} ]
                 [ corrupt PERCENT [CORRELATION]]
                 [ duplicate PERCENT [CORRELATION]]
                 [ loss random PERCENT [CORRELATION]]
                 [ loss state P13 [P31 [P32 [P23 P14]]]
                 [ loss gemodel PERCENT [R [1-H [1-K]]]
                 [ ecn ]
                 [ reorder PRECENT [CORRELATION] [ gap DISTANCE ]]
                 [ rate RATE [PACKETOVERHEAD] [CELLSIZE] [CELLOVERHEAD]]
                 :param reorder_gap:
                 :param reorder_correlation:
                 :param reorder_percent:
                 :param delay_distribution:
                 :param loss_correlation:
                 :param loss_percent:
                 :param duplicate_correlation:
                 :param duplicate_percent:
                 :param corrupt_correlation:
                 :param corrupt_percent:
                 :param delay_correlation:
                 :param delay_jitter:
                 :param delay_time:
                 :param packet_limit:
                 :param operation:
                 :param interface:
    """
    if operation != "add" and operation != "change" and operation != "del":
        return False, "operation should be one of {add|change|del}"

    command = "tc qdisc {op} dev {int} root netem".format(op=operation, int=interface)

    if packet_limit:
        if not isinstance(delay_time, int):
            try:
                packet_limit = int(packet_limit)
            except ValueError:
                return False, "Packet limit should be integer"

        command += " limit {limit}".format(limit=packet_limit)

    if delay_time:
        if isinstance(delay_time, int) or (isinstance(delay_time, str) and "ms" not in delay_time):
            delay_time = "{0}ms".format(delay_time)

        command += " delay {time}".format(time=delay_time)

        if delay_jitter:
            if isinstance(delay_jitter, int) or (isinstance(delay_jitter, str) and "ms" not in delay_jitter):
                delay_jitter = "{0}ms".format(delay_jitter)

            command += " {jitter}".format(jitter=delay_jitter)

            if delay_correlation:
                if isinstance(delay_correlation, int) \
                        or (isinstance(delay_correlation, str) and "%" not in delay_correlation):
                    delay_correlation = "{0}%".format(delay_correlation)
                command += " {corr}".format(corr=delay_correlation)

        if delay_distribution:
            if delay_distribution != "uniform" and delay_distribution != "normal" \
                 and delay_distribution != "pareto" and delay_distribution != "paretonormal":
                return False, "delay_distribution should be one of {uniform|normal|pareto|paretonormal}"

            command += " distribution {dist}".format(delay_distribution)

    if corrupt_percent:
        if isinstance(corrupt_percent, int) or (isinstance(corrupt_percent, str) and "%" not in corrupt_percent):
            corrupt_percent = "{0}%".format(corrupt_percent)

        command += " corrupt {per}".format(per=corrupt_percent)

        if corrupt_correlation:
            command += " {corr}".format(corr=corrupt_correlation)

    if loss_percent:
        if isinstance(loss_percent, int) or (isinstance(loss_percent, str) and "%" not in loss_percent):
            loss_percent = "{0}%".format(loss_percent)

        command += " loss {per}".format(per=loss_percent)

        if loss_correlation:
            command += " {corr}".format(corr=loss_correlation)

    if duplicate_percent:
        if isinstance(duplicate_percent, int) or (isinstance(duplicate_percent, str) and "%" not in duplicate_percent):
            duplicate_percent = "{0}%".format(duplicate_percent)

        command += " duplicate {per}".format(per=duplicate_percent)

        if duplicate_correlation:
            command += " {corr}".format(corr=duplicate_correlation)

    if reorder_percent:
        if isinstance(reorder_percent, int) or (isinstance(reorder_percent, str) and "%" not in reorder_percent):
            reorder_percent = "{0}%".format(reorder_percent)

        command += " reorder {per}".format(per=reorder_percent)

        if reorder_correlation:
            command += " {corr}".format(corr=reorder_correlation)

        if reorder_gap:
            command += " gap {gap}".format(gap=reorder_gap)

    return command

if __name__ == "__main__":
    print(generate_tc_cmd(interface="eth0", operation="add",
                       delay_time=100, delay_jitter="10", corrupt_percent="1",
                       reorder_percent=25, reorder_gap=5)
          )