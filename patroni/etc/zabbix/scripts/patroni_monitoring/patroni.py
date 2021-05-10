#!/usr/bin/python3

import json
import time
import urllib3
import requests
import argparse
import logging
import socket

metrics = {}
TIMEOUT = 3


def get_response(addr, endpoint, port=8008):
    url = "http://{}:{}/{}".format(addr, port, endpoint)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(url, verify=False, timeout=4)
    logging.info("Got metrics for {}".format(url))
    return response.json()


def get_node_metrics(addr):
    logging.debug("Try to get Patroni agent metrics")

    metrics = get_response(addr, "read-only")
    cluster = get_response(addr, "cluster")

    metrics["state"] = (1 if metrics["state"] == "running" else 0)
    metrics["visible_cluster_members"] = len(cluster["members"])
    metrics["db_port_check_failed_cluster_members"] = metrics["visible_cluster_members"] - sum(
        [port_is_open(member['host'], member['port'])
         for member in cluster["members"]]
    )
    logging.debug(json.dumps(metrics, indent=1))
    return metrics


def get_config(addr):
    logging.debug("Try to get Patroni configuration")

    metrics = get_response(addr, "config")
    logging.debug(json.dumps(metrics, indent=1))
    return metrics


def port_is_open(ip, port):
    logging.debug("Checking {}:{}".format(ip, port))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((ip, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except Exception as err:
        metrics['patroni_monitoring_error'] = str_for_zabbix(err)
        return False
    finally:
        s.close()


def str_for_zabbix(s):
    return str(s).replace("'", "").replace("\n", "")[:255]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--addr', help='Host public ip', type=str)
    parser.add_argument('--conf', help='Configuration info',
                        action="store_true")
    parser.add_argument('--debug', help='Debug mode',
                        action='store_true', required=False)
    return parser.parse_args()


def main():
    args = parse_args()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if args.debug else logging.CRITICAL)

    try:
        if args.conf:
            metrics = get_config(args.addr)
        else:
            metrics = get_node_metrics(args.addr)

        metrics['patroni_monitoring_error'] = ''
        metrics['patroni_monitoring_state'] = 1
    except Exception as err:
        metrics['patroni_monitoring_state'] = 0
        metrics['patroni_monitoring_error'] = str_for_zabbix(err)
        logging.info("Script error: {}".format(err))

    print(json.dumps(metrics, indent=4, separators=(',', ':')))


if __name__ == '__main__':
    start = time.time()

    main()

    logging.debug(
        "Script finished in {:.3f} seconds".format(time.time()-start))
