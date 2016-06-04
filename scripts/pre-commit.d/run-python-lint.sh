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
        ${PROJECT_ROOT}/.env/bin/python ${PROJECT_ROOT}/.env/bin/pycodestyle "$file"
        if [[ $? -ne 0 ]]; then
            status=1
        fi
    fi
done < <(git diff --cached --name-status)

exit $status
