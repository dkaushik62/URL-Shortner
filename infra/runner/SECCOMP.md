# Explicit syscall policy

`seccomp.json` is the unmodified default profile from
[Moby 25.0.3](https://github.com/moby/moby/blob/v25.0.3/profiles/seccomp/default.json),
matching the development Docker engine. Moby is licensed under
[Apache License 2.0](https://github.com/moby/moby/blob/v25.0.3/LICENSE).

The runner passes this reviewed profile explicitly because the development daemon
reported an unconfined default. Missing/invalid policy fails closed. Build/test,
candidate Java, acceptance and promoted runtime containers apply it. The submitted
compose service also uses it. This profile is platform infrastructure and cannot
be edited by a runtime agent. Historical live runs preceding this correction did
not have an explicit syscall filter; their other measured isolation controls remain
recorded without retroactive claims.
