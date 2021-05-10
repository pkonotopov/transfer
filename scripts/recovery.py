# -*- coding: utf-8 -*-

from mamonsu.plugins.pgsql.plugin import PgsqlPlugin as Plugin
from .pool import Pooler


class Recovery(Plugin):
    DEFAULT_CONFIG = {
        'enabled': str(False)
    }
    Interval = 60

    AgentPluginType = 'pg'

    key_is_in_recovery = "pgsql.replica.recovery{0}"
    query_is_in_recovery = "SELECT pg_catalog.pg_is_in_recovery() as is_in_recovery;"

    def run(self, zbx):
        result = Pooler.query(self.query_is_in_recovery)
        zbx.send(self.key_is_in_recovery.format('[]'), int(result[0][0]))

    def items(self, template):
        result = ''
        if self.Type == "mamonsu":
            delay = self.plugin_config('interval')
            value_type = Plugin.VALUE_TYPE.numeric_unsigned
        else:
            delay = 5  # TODO check delay
            value_type = Plugin.VALUE_TYPE.numeric_float
        result += template.item({
            'name': 'PostgreSQL: replica status',
            'key': self.right_type(self.key_is_in_recovery)
        })
        return result

    def discovery_rules(self, template):
        rule = {
            'name': 'Replica status discovery',
            'key': self.key_is_in_recovery.format.format('[{0}]'.format(self.Macros[self.Type])),

        }
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
            {'key': self.right_type(self.key_is_in_recovery, var_discovery="{#APPLICATION_NAME},"),
             'name': 'Replica status discovery {#APPLICATION_NAME}',
             'value_type': Plugin.VALUE_TYPE.numeric_unsigned,
             'delay': self.plugin_config('interval')}
        ]
        graphs = [
            {
                'name': 'Replica status discovery {#APPLICATION_NAME}',
                'items': [
                    {'color': 'CC0000',
                     'key': self.right_type(self.key_is_in_recovery, var_discovery="{#APPLICATION_NAME},")},
                ]
            }
        ]
        return template.discovery_rule(rule=rule, conditions=conditions, items=items, graphs=graphs)

    def keys_and_queries(self, template_zabbix):
        result = []
        result.append(
            '{0}[*],$2 $1 -c "{1}"'.format(self.is_in_recovery.format(''), self.query_is_in_recovery))
        print(result)
        return template_zabbix.key_and_query(result)

    # def keys_and_queries(self, template_zabbix):
    #     result = ['{0},{1}'.format("pgsql.is_in_recovery", "echo 0")]
    #     return template_zabbix.key_and_query(result)
