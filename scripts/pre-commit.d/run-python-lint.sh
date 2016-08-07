#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT=$(realpath ${DIR}/../../../)

status=0

while read st file; do
    # skip deleted files
    if [ "$st" == 'D' ]; then
        continue;
    fi

    # run lint only on python files
    if [[ "$file" =~ \.py$ ]]; then
        autopep8_output=$(${PROJECT_ROOT}/.env/bin/python ${PROJECT_ROOT}/.env/bin/autopep8 --in-place -aa -vv "$file" 2>&1)

        if [[ $? -ne 0 ]]; then
            status=1
        elif [[ "$(printf "$autopep8_output" | grep -E '[1-9][0-9]* issue' -o)" != "" ]]; then
            printf "$autopep8_output"
            echo
            status=1
        fi
    fi
done < <(git diff --cached --name-status)

exit $status
