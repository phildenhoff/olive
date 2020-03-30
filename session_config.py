import yaml

class SessionConfig:
    homeserver: str = None
    matrix_id: str = None
    password: str = None
    next_batch_file: str = None

    def __init__(self):
        with open('config.yml', 'r') as file:
            config = yaml.safe_load(file)
            required_settings = ["username", "password", "base_url",\
                "next_batch_file"]
            for name in required_settings:
                if name not in config:
                    print(f"Your configuration file {file.name} must have" +\
                          f"{name} field.", file=sys.stderr)
                    sys.exit(1)

                self.__setattr__(name, config[name])

            if "matrix_url" not in config:
                matrix_url = "matrix." + config['base_url']
            else:
                matrix_url = config["matrix_url"]
    
            self.homeserver = f"https://{matrix_url}"
            self.matrix_id = f"@{config['username']}:{config['base_url']}"
            self.password = config["password"]
            self.next_batch_file = config["next_batch_file"]