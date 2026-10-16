# Method mapping and experimental interpretation

All methods start from the same unmodified PI0.5 v44 weight and processor
files. This repository implements method adaptations, not replacements for
the authors' released checkpoints. Default hyperparameters are starting
recipes, not tuned results. Select hyperparameters on development shards.

## Slow Loop: Always Expansion + Merge (α=0.8)

This control copies the main hgpu1 slow loop as of 2026-09-14, including its
native full-policy SFT trainer, source sampler and full-delta composition code.
It always expands once per task and applies the fixed uniform coefficient 0.8
to that task's vision, language and action delta. Previously merged deltas keep
their coefficients. It performs no online steering, verifier decision, remedy
reuse, coefficient search or production registry promotion.

The initial policy is v44. Current/previous/original-LIBERO replay transition
mass is 50/25/25, or 50/0/50 at the first task. The same corrected, precollected
demonstrations used by CLARE/MLR-IFA are read through a process-local input
adapter. Native replay states and orientation are preserved; camera size is
128×128 for mixed batches. The unmodified main trainer handles full-policy
optimization with microbatch 4, accumulation 8 and 1000 updates per task.

Every merged stage is evaluated on all seen tasks using fixed development
contexts, two episodes per task. These observations do not control acceptance
or hyperparameters. The 20-stage lower-triangular matrix supports mean seen-task
success, best-past forgetting and backward transfer. Empty future cells are
never interpreted as failures. See the [experiment configuration and output
contract](experiments/env_position20_20260910/slow_loop_expansion_a08_20260914/README.md).

## CLARE

Source: [CLARE paper v2](https://arxiv.org/html/2601.09512v2),
[official repository](https://github.com/tum-lsy/clare).

Preserved: parallel bottleneck adapters, a new autoencoder discriminator for
each task at each selected layer, normalized reconstruction-error novelty,
reuse through discriminator-to-adapter links, forced shallowest expansion if
no layer signals novelty, adapter training before discriminator training,
frozen historical parameters, and task-ID-free inference.

Adaptation: every PI0.5 action-expert FFN is selected. The official default
condition projection / DiT widths do not exist in PI0.5. Bottleneck=128 and
gamma=1.0 are configurable. Each discriminator sees mean-pooled chunk-token
features, and its selected adapter applies to that sample's entire chunk.
This avoids switching adapters independently at each token. Compared with
the pre-existing `mode_gate` CLARE prototype, all operational code and stage
artifacts for this experiment live under the independent baseline entrypoint.

## MLR-IFA

Source: [MLR-IFA paper](https://arxiv.org/html/2603.10929v2), local official
`lifelong_mlr_ifa/libero/lifelong/algos/mlr.py` and `algos/base.py`.

Preserved: frozen multimodal encoders, replay without old raw camera inputs,
temporal/action decoder adaptation, task-balanced memory, selection of task
pairs by the intersection of high language and visual similarity, and the
angular hinge `relu(theta_positive - theta_negative + gamma * phi)`.

Adaptation: cache uncompressed PI0.5 prefix embeddings in their native dtype and exact masks,
including its tokenized state. Recompute the frozen language-transformer KV
cache from these tokens. Store original normalized 50x7 action targets and
padding masks; no token pooling/compression changes the policy's conditioning.
Only the action expert and its action/time projections learn.
Trainable master weights and optimizer states use FP32 with BF16 autocast
for matrix operations, so small optimizer updates are not rounded away.

PI0.5's action features are 1024D and language embeddings 2048D. A trainable
auxiliary action-feature-to-language projection defines the IFA comparison;
it is trained with the decoder and unused at inference. Language prototypes
use instruction-only tokenizer embeddings rather than discretized-state text.

Exact PI0.5 latents can be larger than raw compressed images. **No memory
compression advantage is assumed.** Active retained bytes include serialized
latent records and task prototypes; input preparation caches and immutable
historical experiment archives are reported separately. Only retained indices
are available to the next task's training sampler. The active budget does not
include the base model or optimizer; report those model costs separately.

## Continual VLA RL

Source: [Simple Recipe Works](https://arxiv.org/html/2603.11653v3),
[official repository](https://github.com/UT-Austin-RobIn/continual-vla-rl).

Preserved: one sequentially updated LoRA policy, on-policy environmental
rollouts, grouped relative returns and clipped policy-gradient updates;
no rehearsal, distillation, or behavioral cloning replaces the RL objective.

Adaptation: the original OpenVLA/OFT token policy is replaced by a PI0.5
stochastic flow policy. At each denoising transition,
`x_next ~ Normal(x - v_theta(x,t)/N, transition_std² I)`. Store the sampled
50x32 latent transition and its old Gaussian log density. Sum log densities
over all latent coordinates and apply a clipped ratio per denoising transition
with the group's success advantage. The fixed initial Gaussian cancels out.
This is a denoising-MDP policy-gradient surrogate, not a marginal action
likelihood or a product ratio over the whole episode. Evaluation keeps the
same stochastic transition distribution.

The π0.5 VLM remains frozen and LoRA covers action-expert attention and FFNs.
This differs from applying LoRA to an entire OpenVLA language backbone and
must be named in comparisons. Mixed-success groups are necessary for a
nonzero GRPO update; skip and count all-equal groups. Optimizers restart at
task boundaries; saved artifacts resume completed stages only.

## RL²-VLA

Source: [RL²-VLA paper](https://arxiv.org/html/2607.26991v2),
[official release](https://github.com/marmotlab/RL2-VLA), and QAM implementation
at commit [`56084df5`](https://github.com/rl2-vla/qam/blob/56084df5a17bec4bfd55e8bf881754e551e329c0/agents/qam.py).

Preserved: frozen VLA action-expert latents, a behavior flow and an
adjoint-matched offline-RL flow, pessimistic TD ensemble and EMA targets,
backward adjoint recursion through a frozen behavior prior, clipped Gaussian
composition weights, latent LSTM failure prediction, calibrated triggering,
and an independently trained candidate verifier.

QAM is implemented in PyTorch with no JAX dependency or submodule install.
It preserves the core slow/fast/QAM objectives; optional FQL distillation and
edit-policy variants are not enabled. QAM time is noise→action while PI0.5
time runs in the opposite direction. Compose `-v_QAM(x,1-t)` with the PI0.5
velocity. Steering affects the executed first 10x7 coordinates by default;
the rest of the 50x32 internal flow follows v44. Normalized action clipping
is configurable (default ±3), rather than reusing Bridge's [-1,1] statistics.

Port-specific differences: use local PRO behavior rollouts, not Bridge/DROID;
replace the incompatible Bridge CoVer checkpoint with an independent latent
+ executed-action success MLP. The LSTM is trained with class-balanced
episode sampling and BCE. Use held-out successful **episode maxima** for an
anytime conformal band rather than per-task, per-timestep SAFE CP bands. Do
not describe this detector as an exact reproduction of every SAFE training
regularizer. Calibration and validation states never occur in training.
The conformal coverage interpretation additionally requires exchangeable
calibration/test episodes; repeated fixed states and a balanced task schedule
alone do not establish that assumption. Report the measured held-out trigger
rate instead of claiming an unconditional coverage guarantee.

`trigger=always` and `trigger=never` are supported ablations of the same
trained steering/scoring modules. Raw v44 is separately evaluated without an
artifact. None of these variants gets the production counterfactual replay
labels for free. Count offline rollout collection and detector training in
their total cost.

## Shared benchmark contract

Read the existing checksum-validated 40-cell LIBERO-PRO manifest. Training
uses only `demo_online_pool`; public evaluation exposes development policy
shards and never opens final-sealed. The first implementation focuses on
policy baselines: it does not add production ticket generation, human-service
launch, automatic deployment, or promotion to the baseline methods.

For all methods, distinguish policy/data acquisition cost, stored model and
memory size, inference candidates and latency, and success after each stage.
The 40 underlying LIBERO tasks are pretrained by v44; these are adaptation
experiments on PRO shifts, not claims that the underlying task identities
were absent from pretraining.
