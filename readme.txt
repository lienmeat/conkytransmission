1) install conky (tested with the conky-all package or all compile options on)
2) install transmission-cli and UNINSTALL transmission-daemon if installed
3) in the transmission GUI, go to edit/preferences/Web-tab and enable the web client
4) run the install.sh (file located inside this directory)
5) Start conky and transmission and download some torrents!

NOTE:
install.sh will add the lines to ~/.conkyrc that conkytransmission needs to run, but will first backup your existing ~/.conkyrc
file to ~/.conkyrc_bkp.  If you do not have a ~/.conkyrc file, a functional sample file will be created for you
(unfortunately if the necessary lines already exist, duplicate lines are added presently in this version of the script)

After install, all templates, documentation and source code can be located in ~/.conkytransmission

conkytransmission was programmed by Eric Lien and is licensed Creative Commons.  Feel free to do with it as you wish, but please
give credit where credit is due.

conkytransmission was developed and tested on Ubuntu 10.04 x86_64 with python v2.6.5, conky v1.8.0, and transmission 2.04
