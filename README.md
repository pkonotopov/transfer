# Zabbix and Grafana templates

The ['templates'](templates/) folder contain Zabbix templates and monitoring dashboards for Grafana.

## Some diagnostic commands to investigate Zabbix metrics

### Install needed packages 
```shell
yum install zabbix-get zabbix-sender -y
```

### Increase and decrease Zabbix Agent logging level
```shell
sudo -u zabbix zabbix_agentd -R log_level_increase
sudo -u zabbix zabbix_agentd -R log_level_decrease
```
### Get metrics
```shell
sudo -u zabbix zabbix_agentd -t "custom.vfs.discover_disks"
sudo -u zabbix zabbix_agentd -t "custom.vfs.discover_disks"
```


### View result of low level discovery
```shell
zabbix_get -s zabbix.server.ip -k "custom.vfs.discover_disks"
```

### View statistics for 'sda' disk
```shell
zabbix_get -s zabbix.server.ip -k "custom.vfs.dev.write.sectors[sda]"
```

