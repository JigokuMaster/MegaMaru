# MegaMaru
MEGA (mega.nz) Downloader for Symbian S60.

# Note:

This is a work in progress. The app can be used, but it is still not working properly.

# Requirements:
Python for S60 version 2.0 (S60v3 and above)

# Features:
* Folder Browser.
* Simple file downloader.
* Bookmarks (EPOC Archive pinned).
* History.

# Issues & limitations:
* When you open a folder for the first time. the operation can take time to fetch and decrypt files information.

* Sometimes, the network/decrypting/background operations can not be canceled immediately.

* No timeout for network operations.

* Downloads can not be resumed.

# Resources & Libraries:

the following libraries were used to make this project.

* [mega.py](https://github.com/odwyersoftware/mega.py)
* [pycrypto-2.6.1](https://github.com/pycrypto/pycrypto)
* [simplejson](https://github.com/simplejson/simplejson)
* [PyS60TLS](https://github.com/JigokuMaster/PyS60TLS) 

