from Crypto import Random
from Crypto.Hash import MD5

import argparse
import getpass

from ironic_neutron_plugin.db import models


def gen_key():
    key = Random.new().read(64)
    return MD5.new(data=key).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Utilites for managing encrypted switch credentials.')
    parser.add_argument("command", help='Run command', choices=['gen_key', 'encrypt', 'decrypt'])
    parser.add_argument('--value', help='Value to encrypt/decrypt')

    parsed_args = parser.parse_args()

    if parsed_args.command == 'gen_key':
        print 'Generated AES Key:'
        print gen_key()
    else:

        key = getpass.getpass('Key: ')

        value = parsed_args.value
        if not value:
            raise ValueError('Must specify --value for encrypt/decrypt')

        if parsed_args.command == 'encrypt':
            print 'Encrypted Value:'
            print models.aes_encrypt(key, value)
        else:
            print 'Decrypted Value:'
            print models.aes_decrypt(key, value)

if __name__ == "__main__":
    main()
