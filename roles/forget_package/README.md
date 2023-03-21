# `forget_package`

In order to make the transition to the binary packges as smooth as possible,
this is a *horrible* role which you should never use that 'forgets' a package
from the `dpkg` database.  This helps us avoid the service being shutdown.
