from oslo.config import cfg

ironic_opts = [
    cfg.BoolOpt("dry_run",
                default=False,
                help="Log only, but exersize the mechanism."),
    cfg.StrOpt("credential_secret",
               help=("Secret AES key for encrypting switch credentials "
                     " in the datastore."))
]

cfg.CONF.register_opts(ironic_opts, "ironic")
