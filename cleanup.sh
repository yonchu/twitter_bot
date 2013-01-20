#!/bin/sh
cwd=$(cd "$(dirname "d0")" && pwd)

list=(record.txt
      sample_bot.db
      twitter_bot.egg-info
      dist
      build)

for item in "${list[@]}"; do
    if [ -e $item ]; then
        echo "Remove $item"
        rm -r "$item"
    fi
done

echo 'Remove *.pyc'
cmd_xargs=xargs
[ $(uname -s) = 'Darwin' ] && cmd_xargs=gxargs
find . -type f -name '*.pyc' -print0 | $cmd_xargs -0 ls -1a
find . -type f -name '*.pyc' -print0 | $cmd_xargs -0 rm -f
