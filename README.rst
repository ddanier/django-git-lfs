.. role:: strike
    :class: strike
django-git-lfs
==============

This is a proof of concept git-lfs storage server implementation, see:

* https://github.com/blog/1986-announcing-git-large-file-storage-lfs
* https://github.com/github/git-lfs
* https://github.com/github/git-lfs/blob/master/docs/api.md

TODO, missing features
----------------------

* Secure perms handler for adding new access tokens
* Returning the correct HTTP status codes for responses
* Tests and documentation
* Anything besides beeing a proof of concept ;-)

Done
~~~~

* Authentication
* Bind this to any real world usage -> See https://github.com/ddanier/gitolite-git-lfs

Why a Django based implemtation?
--------------------------------

* Runs on many setups, with many webservers, with many databases, with many …
* Reusable app, so this may be part of some bigger project
* May use Django storage backends (Amazon S3, Dropbox, …), see https://www.djangopackages.com/grids/g/storage-backends/
* I personally like it :)


