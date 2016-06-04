#!/usr/bin/env sh

if [ ! -e .git/hooks/pre-commit.d ]; then
    mkdir .git/hooks/pre-commit.d
fi

cp scripts/pre-commit .git/hooks/
cp -Ra scripts/pre-commit.d/* .git/hooks/pre-commit.d/
