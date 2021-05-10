# -*- coding: utf-8 -*-

from mamonsu.plugins.pgsql.plugin import PgsqlPlugin as Plugin
from distutils.version import LooseVersion
from .pool import Pooler


class Xlog(Plugin):
    DEFAULT_CONFIG = {'lag_more_than_in_sec': str(60 * 5)}

    # get amount of WAL since '0/00000000'
    query_wal_lsn_diff = " SELECT  pg_catalog.pg_wal_lsn_diff " \
                         "(pg_catalog.pg_current_wal_lsn(), '0/00000000');"

    query_xlog_lsn_diff = "SELECT  pg_catalog.pg_xlog_location_diff " \
                          "(pg_catalog.pg_current_xlog_location(), '0/00000000');"

    # get time of replication lag
    query_agent_replication_lag = "SELECT CASE WHEN extract(epoch from now()-pg_last_xact_replay_timestamp()) " \
                                  "IS NULL THEN 0 ELSE extract(epoch from now()-pg_last_xact_replay_timestamp()) END"
    # get recovery state
    query_is_in_recovery = "SELECT pg_catalog.pg_is_in_recovery();"

    # for discovery rule for name of each replica
    key_lsn_replication_discovery = "pgsql.replication.discovery{0}"
    key_total_lag = 'pgsql.replication.total_lag{0}'
    #  for PG 10 and higher
    key_flush = 'pgsql.replication.flush_lag{0}'
    key_replay = 'pgsql.replication.replay_lag{0}'
    key_write = 'pgsql.replication.write_lag{0}'

    key_wall = 'pgsql.wal.write{0}'
    key_count_wall = "pgsql.wal.count{0}"
    key_replication = "pgsql.replication_lag{0}"
    key_is_in_recovery = "pgsql.is_in_recovery{0}"
    AgentPluginType = 'pg'

    def run(self, zbx):

        # recovery = Pooler.query(self.query_is_in_recovery)
        # zbx.send(self.key_is_in_recovery("[]"), recovery[0][0])

        if Pooler.in_recovery():
            zbx.send(self.key_is_in_recovery('[]'), 1)
            # replication lag
            lag = Pooler.run_sql_type('replication_lag_slave_query')
            if lag[0][0] is not None:
                zbx.send('pgsql.replication_lag[sec]', float(lag[0][0]))
        else:
            zbx.send(self.key_is_in_recovery('[]'), 0)
            Pooler.run_sql_type('replication_lag_master_query')
            if Pooler.server_version_greater('10.0'):
                result = Pooler.query(self.query_wal_lsn_diff)
                result_lags = Pooler.run_sql_type('wal_lag_lsn')
                if result_lags:
                    lags = []
                    for info in result_lags:
                        lags.append({'{#APPLICATION_NAME}': info[0]})
                        zbx.send('pgsql.replication.flush_lag[{0}]'.format(
                            info[0]), info[1])
                        zbx.send('pgsql.replication.replay_lag[{0}]'.format(
                            info[0]), info[2])
                        zbx.send('pgsql.replication.write_lag[{0}]'.format(
                            info[0]), info[3])
                        zbx.send('pgsql.replication.total_lag[{0}]'.format(
                            info[0]), float(info[4]), self.DELTA_SPEED)
                    zbx.send('pgsql.replication.discovery[]',
                             zbx.json({'data': lags}))
                    del lags
            else:
                result = Pooler.query(self.query_xlog_lsn_diff)
                result_lags = Pooler.run_sql_type('xlog_lag_lsn')
                if result_lags:
                    lags = []
                    for info in result_lags:
                        lags.append({'{#APPLICATION_NAME}': info[0]})

                        zbx.send('pgsql.replication.total_lag[{0}]'.format(
                            info[0]), float(info[1]), self.DELTA_SPEED)
                    zbx.send('pgsql.replication.discovery[]',
                             zbx.json({'data': lags}))
                    del lags

            zbx.send(self.key_wall.format("[]"), float(
                result[0][0]), self.DELTA_SPEED)

        # count of xlog files
        if Pooler.server_version_greater('10.0'):
            result = Pooler.run_sql_type('count_wal_files')
        else:
            result = Pooler.run_sql_type('count_xlog_files')
        zbx.send(self.key_count_wall.format("[]"), int(result[0][0]))

    def items(self, template):
        result = ''
        if self.Type == "mamonsu":
            delta = Plugin.DELTA.as_is
        else:
            delta = Plugin.DELTA_SPEED
        result += template.item({
            'name': 'PostgreSQL: wal write speed',
            'key': self.right_type(self.key_wall),
            'units': Plugin.UNITS.bytes,
            'delay': self.plugin_config('interval'),
            'delta': delta
        }) + template.item({
            'name': 'PostgreSQL: streaming replication lag',
            'key': self.right_type(self.key_replication, "sec"),
            'delay': self.plugin_config('interval')
        }) + template.item({
            'name': 'PostgreSQL: count of xlog files',
            'key': self.right_type(self.key_count_wall),
            'delay': self.plugin_config('interval')
        }) + template.item({
            'name': 'PostgreSQL: primary or standby',
            'key': self.right_type(self.key_is_in_recovery),
            'delay': self.plugin_config('interval')
        })
        return result

    def graphs(self, template):
        result = template.graph({
            'name': 'PostgreSQL write-ahead log generation speed',
            'items': [
                {'color': 'CC0000',
                 'key': self.right_type(self.key_wall)}]})
        result += template.graph({
            'name': 'PostgreSQL replication lag in second',
            'items': [
                {'color': 'CC0000',
                 'key': self.right_type(self.key_replication, "sec")}]})
        result += template.graph({
            'name': 'PostgreSQL count of xlog files',
            'items': [
                {'color': 'CC0000',
                 'key': self.right_type(self.key_count_wall)}]})
        return result

    def triggers(self, template):
        return template.trigger({
            'name': 'PostgreSQL streaming lag too high '
                    'on {HOSTNAME} (value={ITEM.LASTVALUE})',
            'expression': '{#TEMPLATE:' + self.right_type(self.key_replication, "sec") + '.last()}&gt;' +
            self.plugin_config('lag_more_than_in_sec')
        })

    def discovery_rules(self, template):
        rule = {
            'name': 'Replication lag discovery',
            'key': self.key_lsn_replication_discovery.format('[{0}]'.format(self.Macros[self.Type])),

        }
        if Plugin.old_zabbix:
            conditions = []
            rule['filter'] = '{#APPLICATION_NAME}:.*'
        else:
            conditions = [
                {
                    'condition': [
                        {'macro': '{#APPLICATION_NAME}',
                         'value': '.*',
                         'operator': None,
                         'formulaid': 'A'}
                    ]
                }

            ]
        items = [
            {'key': self.right_type(self.key_flush, var_discovery="{#APPLICATION_NAME},"),
             'name': 'Time elapsed between flushing recent WAL locally and receiving notification that '
                     'this standby server {#APPLICATION_NAME} has written and flushed it',
             'value_type': Plugin.VALUE_TYPE.text,
             'delay': self.plugin_config('interval')},
            {'key': self.right_type(self.key_replay, var_discovery="{#APPLICATION_NAME},"),
             'name': 'Time elapsed between flushing recent WAL locally and receiving notification that '
                     'this standby server {#APPLICATION_NAME} has written, flushed and applied',
             'value_type': Plugin.VALUE_TYPE.text,
             'delay': self.plugin_config('interval')},
            {'key': self.right_type(self.key_write, var_discovery="{#APPLICATION_NAME},"),
             'name': 'Time elapsed between flushing recent WAL locally and receiving notification that '
                     'this standby server {#APPLICATION_NAME} has written it',
             'value_type': Plugin.VALUE_TYPE.text,
             'delay': self.plugin_config('interval')},
            {'key': self.right_type(self.key_total_lag, var_discovery="{#APPLICATION_NAME},"),
             'name': 'Delta of total lag for {#APPLICATION_NAME}',
             'value_type': Plugin.VALUE_TYPE.numeric_float,
             'delay': self.plugin_config('interval')},
            {'key': self.right_type(self.key_is_in_recovery, var_discovery="{#APPLICATION_NAME},"),
             'name': 'Primary or standby {#APPLICATION_NAME}',
             'value_type': Plugin.VALUE_TYPE.numeric_unsigned,
             'delay': self.plugin_config('interval')}
        ]
        graphs = [
            {
                'name': 'Delta of total lag for {#APPLICATION_NAME}',
                'items': [
                    {'color': 'CC0000',
                     'key': self.right_type(self.key_total_lag, var_discovery="{#APPLICATION_NAME},")},
                ]
            }
        ]
        return template.discovery_rule(rule=rule, conditions=conditions, items=items, graphs=graphs)

    def keys_and_queries(self, template_zabbix):
        result = []
        if LooseVersion(self.VersionPG) < LooseVersion('10'):
            result.append(
                '{0},$2 $1 -c "{1}"'.format(self.key_count_wall.format('[*]'), Pooler.SQL['count_xlog_files'][0]))
            result.append(
                '{0},$2 $1 -c "{1}"'.format(self.key_wall.format('[*]'), self.query_xlog_lsn_diff))
        else:
            result.append(
                '{0},$2 $1 -c "{1}"'.format(self.key_count_wall.format('[*]'), Pooler.SQL['count_wal_files'][0]))
            result.append(
                '{0},$2 $1 -c "{1}"'.format(self.key_wall.format('[*]'), self.query_wal_lsn_diff))
        result.append(
            '{0},$2 $1 -c "{1}"'.format("pgsql.replication_lag.sec[*]", self.query_agent_replication_lag))
        result.append(
            '{0},$2 $1 -c "{1}"'.format("pgsql.replication_lag.sec[*]", self.query_agent_replication_lag))
        result.append(
            '{0},$2 $1 -c "{1}"'.format("pgsql.is_in_recovery[*]", self.query_is_in_recovery))
        return template_zabbix.key_and_query(result)
