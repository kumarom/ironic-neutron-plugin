Switch credentials are stored encrypted with AES in the datastore.

You must generate your own secret key before using this plugin.

```
python crypto.py gen_key

Generated AES Key:
5422035f085eae3129cd32955d6e92d7
```

place the output in neutron.conf

```
[ironic]
credential_key = 5422035f085eae3129cd32955d6e92d7
```
