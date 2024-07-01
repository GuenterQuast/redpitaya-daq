import numpy as np

"""vielen dank chatgpt..."""

class ConfigError(Exception):
    """Custom exception to raise when configuration is invalid."""
    pass

def requires_keys(*required_keys):
    """Decorator to ensure required keys are present in the configuration."""
    def decorator(method):
        def wrapper(self, *args, **kwargs):
            if not all(key in self.config for key in required_keys):
                missing_keys = [key for key in required_keys if key not in self.config]
                raise ConfigError(f"Missing required config keys: {', '.join(missing_keys)}")
            return method(self, *args, **kwargs)
        return wrapper
    return decorator


def map(input_dict,list_of_keys):
    output_dict = {}
    # check if list_of_keys matches keys of input_dict
    if not all(key in input_dict for key in list_of_keys):
        raise ConfigError(f"Keys in list_of_keys do not match keys in input_dict")
    if not isinstance(input_dict, dict):
        for key in list_of_keys:
            output_dict[key] = input_dict



# HMmm is net the way to go...
class Filter:
    def __init__(self, config_dict):
        self.config_dict = config_dict
        self.list_of_keys = config_dict['list_of_keys']
        
    def map(self, config):
        input_dict = self.config_dict[config]
        output_dict = {}
        if isinstance(input_dict, dict):
            # check if list_of_keys matches keys of input_dict
            if not all(key in input_dict for key in self.list_of_keys):
                raise ConfigError(f"Keys in list_of_keys do not match keys in {config}")
        
            for key in list_of_keys:
                output_dict[key] = input_dict
        
    @requires_keys('clipping_level')
    def check_clipping(self, input_data):
        """
        Check if any channel in the input data exceeds the specified clipping value.

        Args:
            input_data (numpy.ndarray): The input data.
            clipping_level (float): The maximum absolute value allowed for each channel.

        Returns:
            bool: True if any channel exceeds the clipping value, False otherwise.
        """
        self.clipping_level = self.config_dict['clipping_level']
        for channel in input_data.dtype.names:
            if np.max(input_data[channel]) >= self.clipping_level or np.min(input_data[channel]) <= -self.clipping_level:
                return True
        return False

    









