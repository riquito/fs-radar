fs_radar
========

fs_radar executes commands when a matching file is touched.


How to run
----------

```sh
./bin/fs_radar -c config.toml
```

Config file
-----------

This is the simplest config file, it will monitor the file  README.md. If it's
touched fs-radar will print a warning.

```toml
[fs_radar]
basedir = '/home/foo/myproject/'
[group.choose_your_name]
rules = '''
./README.md
'''
cmd = "echo {} has been touched"
```
The config file is written in [toml](https://github.com/toml-lang/toml). It
must always contain a `fs_radar` field holding global configurations and one or
many fields named `group.[whatever]` with specific configurations to run a
command.

The field `fs_radar` requires at least the value `basedir` (as an absolute
path). It will be used as base path to match whatever relative path you wrote
in a `group.*` field.

As you may have guessed, any occurrence of `{}` in a `cmd` option will be
replaced by the path of the touched file (you don't have to worry about
whitespaces or quoting). The path will be relative to `basedir`.

Config file options
-------------------

### [fs_radar] ###

**basedir** [string, required]

Path to the directory holding the files matched by the rules (rules act on
relative paths).

**<a name="bash_profile">bash_profile</a>** [string|boolean] default: `false`

Set it to `false` if you don't want to source the default bash init file
(e.g. `~/.bash_profile`) before running a command.
If `true` it will use the bash init file loaded during a login with bash.
If it's a string it must be the path to a bash init file that will be loaded
before running your command. You probably want to use this option if you
need your favorite shell `alias`.

If both `stop_previous_process` and `discard_if_already_running` are set to
`true` then `discard_if_already_running` takes precedence.

If both `stop_previous_process` and `discard_if_already_running` are set to
`false` (the default) then the match event will be put on an hold and a new
process will spawn when the current process terminates naturally.

You can either set it globally inside the field [fs_radar] or on a per group
basis.

**<a name="discard">discard_if_already_running</a>** [boolean] default: `false`

If `true` and a match happens before the previously executed process
terminated, the new event is discarded and the previous process continues to
run.

You can either set it globally inside the field [fs_radar] or on a per group
basis.

**<a name="stop_process">stop_previous_process</a>** [boolean] default: `false`

If `true` and a match happens before the previously executed process
terminated, that process stopped and a new one started.

You can either set it globally inside the field [fs_radar] or on a per group
basis.

**timeout** [int] default: `30`

Amount of time, in seconds, after which a process is interrupted (SIG_TERM
first and, if it wasn't enough, SIG_KILL after `2` seconds).

You can either set it globally inside the field [fs_radar] or on a per group
basis.

### [group.*] ###

**cmd** [string, required]

The command to run when a `rule` match. Any occurrence of `{}` will be replaced
by the path of the touched file, relative to `basedir`. It's automatically
quoted.

**rules** [string|list, required]

List of rules to detect if the change of a file must trigger `cmd`.
You can either use a list or a multiline string (suggested).
Empty lines and lines starting with '#' will be ignored.
A rule tries to match a path relative to `basedir`.
fs_radar will start to watch files at any level of `basedir` that may match
`rules`.
If a `rule` matches then `cmd` will be executed.
The format of a rule is similar to a glob pattern.
Single asterisk `*` means "accept zero or more characters inside the directory.
Double asterisk `**` means "accept zero or more characters inside the directory
 and at any level deeper".

```
# example 1
./foo/*bar/**/baz
```

will search for the file `baz`, a descendant of a directory whose name ends
with `bar` and it's a direct child of `foo`.

Note that `baz` may be a direct child of `*bar` too.

```
# example 2
*.txt
```

matches any file ending with `.txt`


Warning: non relative paths like `*.txt` are discouraged because fs_radar
must watch every directory to see if such file is touched.
The same warning, in a lesser degree, is applied to  `**` too. Try to
avoid it or to limit the number of directories that will be watched (if
you can).


**discard_if_already_running** [boolean] default: `false`

Identical to the [homonym global option](#discard), but at group level.

**stop_previous_process** [boolean] default: `false`

Identical to the [homonym global option](#stop_process), but at group level.

**bash_profile** [string|boolean] default: `false`

Identical to the [homonym global option](#bash_profile), but at group level.


Development
-----------

You must use the provided git pre-commit hooks (e.g. autopep8 linter).
Run `provision.sh` when you clone the project and whenever a provisionable
file is updated.

License
-------

GPLv3
