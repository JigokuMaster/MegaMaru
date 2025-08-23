# MegaMaru
MEGA (mega.nz) Downloader for Symbian S60. 

# Note: 

The app is generally safe for basic usage, but some functions are still not optimized yet , use it at your own risk. 

# Requirements:
Python for S60 version 2.0, should work on any S60v3 device,  there is an issue with the Listbox on touchscreen devices it will be fixed in the next update. 

# Features:
* Folder Browser.
* Simple file downloader.
* Bookmarks.
* History.


# Issues & limitations:
* When you open a folder for the first time. the operation can take time to fetch and decrypt files information. 

* Sometimes, the network/decrypting/background operations can not be canceled immediately. 

* Downloads can not be resumed. 

# Resources & Libraries: 

the following libraries were used to make this project. 

* [mega.py](https://github.com/odwyersoftware/mega.py)
* [pycrypto-2.6.1](https://github.com/pycrypto/pycrypto)
* [simplejson](https://github.com/simplejson/simplejson)
* [PyS60TLS](https://github.com/JigokuMaster/PyS60TLS)