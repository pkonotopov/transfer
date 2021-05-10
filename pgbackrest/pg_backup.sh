#jinja2:lstrip_blocks: True
#!/bin/bash
# PostgreSQL backup script for pgbackrest


set -e

# create lockfile
LOCKFILE=/tmp/lock.txt
if [ -e ${LOCKFILE} ] && kill -0 `cat ${LOCKFILE}`; then
  echo "Backup script is already running"
  exit
fi

# make sure the lockfile is removed when we exit and then claim it
trap "rm -f ${LOCKFILE}; exit" INT TERM EXIT
echo $$ > ${LOCKFILE}

# Configure script
POSTGRES_HOST_USER="postgres"
PGBACKREST_BACKUP_FOLDER="/var/lib/pgbackrest"
PGBACKREST_CONFIG_DIR="/etc/pgbackrest"
PGBACKREST_STANZA="demo"

# Enable sudo command if we are root
SUDO=""
if (( $EUID==0 )); then
  SUDO="sudo -u $POSTGRES_HOST_USER"
fi

# Do not run this script as a non-privileged user!
function is_true() {
  if [[ "${@}" =~ (root|"$POSTGRES_HOST_USER") ]]; then return 0; fi
  return 1
  }

BACKUP_COMMAND="pgbackrest  \
        --config-path=$PGBACKREST_CONFIG_DIR \
        --stanza=$PGBACKREST_STANZA"


function init {

# Create backup folder if not

if [ -d "$PGBACKREST_BACKUP_FOLDER" ]
then
  echo "INFO: Backup directory exists"
else
  echo "WARNING: Backup directory does not exists"
  echo "INFO: Creating backup directory"
  mkdir -p $PGBACKREST_BACKUP_FOLDER
  chown $POSTGRES_HOST_USER:$POSTGRES_HOST_USER $PGBACKREST_BACKUP_FOLDER -R
fi

# Add stanza if not

if [ -d "$PGBACKREST_BACKUP_FOLDER/{backup,archive}/$PGBACKREST_STANZA" ]
then
  echo "INFO: Stanza $PGBACKREST_STANZA exists in backup folder"
else
  echo "WARNING: Instance $PGBACKREST_STANZA does not exists in backup folder"
  echo "INFO: Adding $PGBACKREST_STANZA to backup folder"
  $SUDO $BACKUP_COMMAND stanza-create
  echo "WARNING: Create first full backup"
fi
}

# Make FULL backup

function backup_full {

if [ -d "$BACKUP_FOLDER/backup" ]
then
  echo "INFO: Doing FULL backup"
else
  init
fi

$SUDO $BACKUP_COMMAND --type=full backup

}

# Make DIFF backup

function backup_diff {

if [ -d "$PGBACKREST_BACKUP_FOLDER/archive/$PGBACKREST_STANZA" ]
then
  echo 'Stanza exists, continue...' >&2
else
  echo "WARNING: Seems like backup directory was not inited"
  exit 1
fi

if $SUDO $BACKUP_COMMAND --type=diff backup
then
  echo "INFO: Diff backup was done"
  exit 0
else
  echo "WARNING: Diff backup was failed. Doing FULL backup"
  $SUDO $BACKUP_COMMAND --type=full backup
fi

}

usage="$(basename "$0") [-h] OPTION -- script for creating backup for PostgreSQL

where:
    -h       show this help text
    --full   create full backup
    --diff   create diff backup
    --info   show backups"

if [ -z $* ]
then
    echo "You must provide at least one optioni:"
    echo "$usage"
    exit 1
fi

if is_true "$(whoami)"; then
  case "$1" in
    -h | --help) echo "$usage"
             exit
             ;;
         --full) backup_full
             ;;
         --diff) backup_diff
             ;;
         --info) $SUDO $BACKUP_COMMAND info
             ;;
  esac
else
  echo 'You should be root or postgres user.' >&2
fi

# remove lock file
rm -f ${LOCKFILE}
