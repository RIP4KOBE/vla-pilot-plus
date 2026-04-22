# test/pi05_loading.py
import os, sys, time, traceback

print("[1] script start", flush=True)
print("[2] python:", sys.version, flush=True)
print("[3] cwd:", os.getcwd(), flush=True)

t0 = time.time()
try:
    print("[4] importing lerobot...", flush=True)
    import lerobot
    print("[5] lerobot imported:", getattr(lerobot, "__version__", "no __version__"), flush=True)

    print("[6] importing PI05Policy...", flush=True)
    from lerobot.policies.pi05 import PI05Policy
    print("[7] PI05Policy imported", flush=True)

    model_id = "lerobot/pi05_libero_finetuned_v044"
    print(f"[8] loading from_pretrained({model_id}) ...", flush=True)

    policy = PI05Policy.from_pretrained(model_id)
    print("[9] loaded policy OK", flush=True)

    # 尽量打印一些关键结构信息
    sd = policy.state_dict()
    print("[10] state_dict keys:", len(sd), flush=True)
    # 检查你之前报错相关的key大类是否存在
    def has(substr): 
        return any(substr in k for k in sd.keys())
    print("[11] has embed_tokens.weight?", has("embed_tokens.weight"), flush=True)
    print("[12] has input_layernorm.weight?", has("input_layernorm.weight"), flush=True)
    print("[13] has input_layernorm.dense.weight?", has("input_layernorm.dense.weight"), flush=True)

except Exception as e:
    print("[X] exception:", repr(e), flush=True)
    traceback.print_exc()
finally:
    print("[Z] elapsed:", round(time.time() - t0, 2), "sec", flush=True)