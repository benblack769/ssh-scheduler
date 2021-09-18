echo "one job"
echo "jobs will tell you if they fail" && exit 1
echo "another job" && echo "a combined job (bash syntax applies)"
bash local.sh && echo "you can also call local files because they are copied by the remote by the default value of --copy-forwards"
