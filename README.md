# Tacata

Tacata creates Netkit and Kathará labs using a single file and a simple syntax.
To date, only an old version of Tacata is available in the branch named `old`.

**This is the old version of Tacata. It has not been tested on Kathará.**

# Brief Tutorial

To create a new lab, a file named `lab.confu` is required. This files contains
the Netkit net configuration as well as additional information used by Tacata.

Run `python tacata.py` in the folder containing the `lab.confu` to create the lab.

# Examples

Examples are provided in the `example` folder. Those examples are the solutions to
some Netkit exams available [here](http://wiki.netkit.org/index.php/Labs_Exams).
Keep in mind that DNS is not available in this old version of Tacata and that
BGP is only partially supported. Therefore, some additional configuration might
be needed.