import numpy as np
import configparser


def getconf_resix(hconfig: configparser.ConfigParser):

    try:
        resi_ranges = []
        for protomer in hconfig.get("sequence_features", "protomers").split(":"):
            start, end = protomer.split("-")
            resi_ranges += list(range(int(start)-1, int(end)))

        return np.array(resi_ranges, dtype=np.int32)

    except (configparser.NoOptionError, configparser.NoSectionError):
        return None


def getconf_chains(hconfig: configparser.ConfigParser):

    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

    try:
        resiD = {}
        ix = 1
        for cix, protomer in enumerate(hconfig.get("sequence_features", "protomers").split(":")):
            chain_id = letters[cix]
            start, end = protomer.split("-")
            for jx in range(int(start), int(end)+1):
                resiD[ix] = f"{chain_id}{jx:4d}"
                ix += 1

        return resiD

    except (configparser.NoOptionError, configparser.NoSectionError):
        return None
