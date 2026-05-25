from core.policy_observation_sampling import policy_observation_sample_num


def test_rdt_fetches_single_online_observation_even_with_particle_batch_size():
    assert policy_observation_sample_num("rdt", 20) == 1


def test_non_rdt_policies_use_configured_sample_batch_size():
    assert policy_observation_sample_num("pi05", 20) == 20
    assert policy_observation_sample_num("diffusion", 20) == 20


def test_non_rdt_policies_default_to_twenty_when_unconfigured():
    assert policy_observation_sample_num("pi05", None) == 20
