def policy_observation_sample_num(policy_type, configured_sample_batch_size, default=20):
    if policy_type == "rdt":
        return 1
    return int(default if configured_sample_batch_size is None else configured_sample_batch_size)
