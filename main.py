#@title Imports and Notebook Utilities
import os
import PIL.Image, PIL.ImageDraw
import numpy as np
import matplotlib.pylab as pl
# from IPython.display import Image, HTML, Markdown, clear_output
from tqdm import  tnrange, tqdm
os.environ['FFMPEG_BINARY'] = 'ffmpeg'
import torch
import torchvision.models as models
import torch.nn.functional as F
# torch.set_default_tensor_type('torch.cuda.FloatTensor')
from dataclasses import dataclass

@dataclass
class Config:
    hidden_n: int = 96
    state_dim: int = 12
    update_rate: float = 0.5

config = Config()

import gc
from utils import imread, imshow, VideoWriter, grab_plot, zoom

#@title VGG16 Sliced OT Style Model
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
vgg16 = models.vgg16(weights='IMAGENET1K_V1').features.to(device)


def calc_styles_vgg(imgs):
  style_layers = [1, 6, 11, 18, 25]  
  mean = torch.tensor([0.485, 0.456, 0.406], device=device)[:,None,None]
  std = torch.tensor([0.229, 0.224, 0.225], device=device)[:,None,None]
  x = (imgs-mean) / std
  b, c, h, w = x.shape
  features = [x.reshape(b, c, h*w)]
  for i, layer in enumerate(vgg16[:max(style_layers)+1]):
    x = layer(x)
    if i in style_layers:
      b, c, h, w = x.shape
      features.append(x.reshape(b, c, h*w))
  return features

def project_sort(x, proj):
  return torch.einsum('bcn,cp->bpn', x, proj).sort()[0]

def ot_loss(source, target, proj_n=32):
  ch, n = source.shape[-2:]
  projs = F.normalize(torch.randn(ch, proj_n, device=device), dim=0)
  source_proj = project_sort(source, projs)
  target_proj = project_sort(target, projs)
  target_interp = F.interpolate(target_proj, n, mode='nearest')
  return (source_proj-target_interp).square().sum()

def create_vgg_loss(target_img):
  yy = calc_styles_vgg(target_img)
  def loss_f(imgs):
    xx = calc_styles_vgg(imgs)
    return sum(ot_loss(x, y) for x, y in zip(xx, yy))
  return loss_f

def to_nchw(img):
  img = torch.as_tensor(img)
  if len(img.shape) == 3:
    img = img[None,...]
  return img.permute(0, 3, 1, 2)

ident = torch.tensor([[0.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,0.0]])
sobel_x = torch.tensor([[-1.0,0.0,1.0],[-2.0,0.0,2.0],[-1.0,0.0,1.0]])
lap = torch.tensor([[1.0,2.0,1.0],[2.0,-12,2.0],[1.0,2.0,1.0]])

def perchannel_conv(x, filters):
  '''filters: [filter_n, h, w]'''
  b, ch, h, w = x.shape
  y = x.reshape(b*ch, 1, h, w)
  y = torch.nn.functional.pad(y, [1, 1, 1, 1], 'circular')
  y = torch.nn.functional.conv2d(y, filters[:,None])
  return y.reshape(b, -1, h, w)

def perception(x):
  filters = torch.stack([ident, sobel_x, sobel_x.T, lap]).to(device)
  return perchannel_conv(x, filters)

class CA(torch.nn.Module):
  def __init__(self, chn=16, hidden_n=config.hidden_n):
    super().__init__()
    self.chn = chn
    self.w1 = torch.nn.Conv2d(chn*4, hidden_n, 1)
    self.w2 = torch.nn.Conv2d(hidden_n, chn, 1, bias=False)
    self.w2.weight.data.zero_()

  def forward(self, x, update_rate=0.5):
    y = perception(x)
    y = self.w2(torch.relu(self.w1(y)))
    b, c, h, w = y.shape
    udpate_mask = (torch.rand(b, 1, h, w).to(device)+update_rate).floor()
    return x+y*udpate_mask

  def seed(self, n, sz=128):
    return torch.zeros(n, self.chn, sz, sz)

def to_rgb(x):
  return x[...,:3,:,:]+0.5

param_n = sum(p.numel() for p in CA().parameters())
print('CA param count:', param_n)

### target image
url = 'https://www.robots.ox.ac.uk/~vgg/data/dtd/thumbs/dotted/dotted_0201.jpg'
# url = 'computer.webp'

style_img = imread(url, max_size=128)
with torch.no_grad():
  loss_f = create_vgg_loss(to_nchw(style_img).to(device))
imshow(style_img, count=0)

### setup training
ca = CA().to(device)
opt = torch.optim.Adam(ca.parameters(), 1e-3)
lr_sched = torch.optim.lr_scheduler.MultiStepLR(opt, [1000, 2000], 0.3)
loss_log = []
with torch.no_grad():
  pool = ca.seed(256).to(device)

### training loop
gradient_checkpoints = False  # Set in case of OOM problems

for i in range(5000):
  with torch.no_grad():
    batch_idx = np.random.choice(len(pool), 4, replace=False)
    x = pool[batch_idx]
    if i%8 == 0:
      x[:1] = ca.seed(1)
  step_n = np.random.randint(32, 96)
  if not gradient_checkpoints:
    for k in range(step_n):
      x = ca(x)
  else:
    x.requires_grad = True
    x = torch.utils.checkpoint.checkpoint_sequential([ca]*step_n, 16, x)

  overflow_loss = (x-x.clamp(-1.0, 1.0)).abs().sum()
  loss = loss_f(to_rgb(x))+overflow_loss
  with torch.no_grad():
    loss.backward()
    for p in ca.parameters():
      p.grad /= (p.grad.norm()+1e-8)   # normalize gradients 
    opt.step()
    opt.zero_grad()
    lr_sched.step()
    pool[batch_idx] = x                # update pool
    
    loss_log.append(loss.item())
    if i%5 == 0:
      print(f" \
        step_n: {len(loss_log)} \
        loss: {loss.item()} \
        lr: {lr_sched.get_last_lr()[0]}")

    if i%100==0:
      pl.plot(loss_log, '.', alpha=0.1)
      pl.yscale('log')
      pl.ylim(np.min(loss_log), loss_log[0])
      pl.tight_layout()
      imshow(grab_plot(), id='log', count=i)
      imgs = to_rgb(x).permute([0, 2, 3, 1]).cpu()
      imshow(np.hstack(imgs), id='batch', count=i)

    if i % 200 == 0:
      with VideoWriter() as vid, torch.no_grad():
        x = ca.seed(1, 256).to(device)
        for k in tqdm(range(300), leave=False):
          step_n = min(2**(k//30), 8)
          for i in range(step_n):
            x[:] = ca(x)
          img = to_rgb(x[0]).permute(1, 2, 0).cpu().detach().numpy()
          vid.add(zoom(img, 2)) # not here
          del img


with VideoWriter() as vid, torch.no_grad():
  x = ca.seed(1, 256).to(device)
  for k in tqdm(range(300), leave=False):
    step_n = min(2**(k//30), 8)
    for i in range(step_n):
      x[:] = ca(x)
    img = to_rgb(x[0]).permute(1, 2, 0).cpu().detach().numpy()
    vid.add(zoom(img, 2)) # not here
    del img

print('done')


# tenslist = []
# for obj in gc.get_objects():
#     try:
#         if torch.is_tensor(obj) or (hasattr(obj, 'data') and torch.is_tensor(obj.data)):
#             tenslist.append(obj)
#     except:
#         pass
# print(len(tenslist))