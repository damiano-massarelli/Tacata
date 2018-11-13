# Tacatá

Tacatá is a simple Python script which creates Netkit and Kathará labs using an enriched version of the `lab.conf` file with a simple syntax.

You can find some examples of configuration files in `labs` folder.

# !!! WARNING !!!

Keep in mind that Tacatá is only intended to be used during Intermediate Tests for the Infrastructures of Computer Networks course at the Roma Tre University. We're not trying to support all the Kathará features (like P4 programming or NFV approaches). However, you can still create all the files/folders manually in the generated lab.

## How it works

1. Create a `lab.confu` in the directory where `tacata.py` is stored.
2. Write all you need to reproduce the lab in the `lab.confu` file.
3. From a Terminal, launch `python tacata.py`
4. The generated lab will be placed in a new `lab` folder
5. You can normally launch the lab from the `lab` folder without extra steps!

## Currently Supported 
1. Terminals/Routers
2. Web Servers