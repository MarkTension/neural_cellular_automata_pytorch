import torch
import gc
from contextlib import ContextDecorator

def get_n_tensors():
    tenslist = []
    for obj in gc.get_objects():
        try:
            if torch.is_tensor(obj) or (hasattr(obj, 'data') and torch.is_tensor(obj.data)):
                tenslist.append(obj)
        except:
            pass
    return len(tenslist)


class check_memory_leak_context(ContextDecorator):
    def __enter__(self):
        self.start = get_n_tensors()
        return True

    def __exit__(self, *exc):
        self.end = get_n_tensors()
        increase = self.end - self.start
        if increase > 0:
            print(f"num tensors increased" \
                  f"with {self.end - self.start} !")
        else:
            print(f"no added tensors")
        return False