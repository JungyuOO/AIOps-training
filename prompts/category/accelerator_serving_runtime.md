# accelerator_serving_runtime

Broad GPU, RHOAI Workbench, KServe, and model-serving runtime cases.

Include GPU scheduling failures, Workbench GPU contention, device plugin NotReady, CUDA runtime/driver mismatch, `NVIDIA_VISIBLE_DEVICES=void`, vLLM OOM, excessive `max_model_len`, KServe predictor Pending, storage init blocking predictor startup, and long model warmup causing probe failure.

Evidence should name GPU limits, node allocatable GPU, active GPU consumers, InferenceService predictor spec, vLLM args, CUDA logs, and probe settings.
