#!/usr/bin/env sh


test -z "$1" && echo "usage: $0 logdir (which contains [dbname]/[cold|hot] directories)" && exit 1

rundir=$1

echo "db,runtype,query,time_s"
for dbname in $(ls $rundir/ | sort -t'h' -k2 -n); do
    for runtype in $(ls $rundir/$dbname/); do
        # echo $rundir/$dbname/$runtype
        (
            cd $rundir/$dbname/$runtype/;
            jq -r '[input_filename, .operator_timing] | @csv | sub("\"";"";"g") ' *.json \
                | sed -e "s/^/$dbname,$runtype,/"\
                | sed -e "s/\.json//"
        ) | sort -t',' -k2 | sort -t',' -nk3
    done
done 