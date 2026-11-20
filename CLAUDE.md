# Project rules

## No backward compatibility

The Watch Me plugin is not deployed anywhere yet and nobody uses it. When changing
anything (config keys, file formats, recording layout, CLI arguments, timeline output),
do not keep backward compatibility and do not write migrations: rename, remove or
change things directly and update the code, tests and docs that use them.
