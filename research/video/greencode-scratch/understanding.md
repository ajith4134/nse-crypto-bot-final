# Understanding — "I Built a Neural Network from Scratch" (Green Code, ~9:15)

Source: transcript.md (104 segments) + 80 keyframes in frames/.
Frame coverage: 0:03–2:44 and 6:45–9:09. **No frames exist for 3:00–6:45** (loss/backprop/optimizer explanation + bug story) — that span is reconstructed from audio only.

## Summary

The creator builds a fully-working feed-forward neural network using ONLY numpy + Python (explicitly rejecting PyTorch/TensorFlow/Keras, shown on screen at 0:03–0:06). He starts with a single 3-input neuron (weighted sum + bias), scales to a fully-connected multi-layer network computed with `np.dot` per layer, adds ReLU non-linearity on hidden layers and softmax on the output to get a class-probability distribution. He first validates the forward pass alone by importing weights trained in PyTorch (97.53% accuracy), then implements categorical cross-entropy loss, backpropagation via partial derivatives (explained with a "team of chefs" analogy), a learning rate, and a plain SGD optimizer (explicitly skipping momentum/AdaGrad/RMSProp). After debugging (a `backwards(y)` vs `backwards(output)` argument bug, learning-rate and weight-init experiments), he trains on MNIST (60,000 28×28 digit images, 10 classes) reaching 97.42% test accuracy with mini-batches, inspects misclassifications, then retrains the identical code on Fashion-MNIST for 87% accuracy.

## REQUIREMENTS

### A. Scope / philosophy

- **REQ-GRC-01 — From-scratch constraint** [00:00–00:06; f_0003_000, f_0005_001, f_0005_002, f_0007_003]: The network must be implemented with no ML libraries or pre-built frameworks — "only numpy, python and some maths." Frames show PyTorch `torch.nn.Linear` docs, TensorFlow.org and Keras.io as the things NOT used; the project starts as a VS Code file (`numpyRocks!.py`, workspace `neuralFromScratch`) whose first line is `import numpy`.
- **REQ-GRC-02 — Build progression** [00:07–00:15, 09:01–09:10; f_0013_005]: Progression is: individual neuron → layers of neurons → full network → real tasks (MNIST digits, Fashion-MNIST). Frame f_0013_005 shows the end goal up front: an ASCII-art "5" digit fed into a green network diagram whose output column is labeled with digits 9…0.

### B. Single neuron (forward math)

- **REQ-GRC-03 — Neuron = weighted sum + bias** [00:15–00:38; f_0045_010, f_0234_035]: A neuron has N inputs and 1 output; output = Σ(inputᵢ·weightᵢ) + bias. Drawn as **three straight input lines converging into a single circle, with one output line leaving to the right**; labels "INPUTS" (rotated, left) and "OUTPUT" (right). In f_0234_035 the three edges carry concrete example weights **-0.74, 1.37, 0.08** and the circle has **BIAS = -2.37** written above it. Every connection has a weight; the bias belongs to the neuron.
- **REQ-GRC-04 — Learning = tweaking weights & bias** [00:34–00:40]: Learning is defined as adjusting the weights and the bias until the output is what we want (foreshadows backprop).

### C. Network topology & visual arrangement

- **REQ-GRC-05 — Fully-connected layered network drawing** [00:45–01:11; f_0114_011, f_0147_020, f_0208_029, f_0727_093, f_0733_094]: The network is drawn as **vertical columns of circles (layers), left-to-right, with EVERY node in a column connected by a straight line to EVERY node in the next column** (dense green mesh; "all the neurons are interconnected"). Layout details captured from frames:
  - "INPUTS" label rotated vertically at the far left; "OUTPUT" rotated at the far right (f_0114_011, f_0147_020).
  - Hidden columns are drawn TALLER (more nodes) than input/output columns — e.g. f_0147_020: small input column → ~5 tall dense hidden columns → smaller output column.
  - MNIST version (f_0727_093): input column (subset of the 784 pixels shown) → 2 hidden columns (~24 nodes each) → **output column of 10 nodes labeled 9,8,7,6,5,4,3,2,1,0 top-to-bottom**; the drawn digit image sits to the left of the input column.
  - A second small architecture (f_0733_094): 2 input nodes → hidden(8) → hidden(~12) → hidden(8) → 1 output node — used for the sample-data/plot experiments.
  ```
  INPUTS   H1        H2        H3      OUTPUT
   o ----\ o ======= o ======= o ----- o  9
   o -----=o ======= o ======= o ----- o  8
   o -----=o ======= o ======= o  ...  o  ...
   o ----/ o ======= o ======= o ----- o  0
        (every node → every node in next column)
  ```
- **REQ-GRC-06 — Layer value propagation** [01:01–01:11]: Each neuron's value = weighted sum of ALL neurons in the previous layer (+ bias); this repeats layer by layer until the final output.
- **REQ-GRC-07 — Dot product vectorization** [01:16–01:33; f_0129_016]: Replace the per-connection arithmetic with linear algebra. The whole layer computation is one line, transcribed exactly:
  ```python
  for i in range(len(self.weights)):
      # Dot Product to ...
      layers.append(np.dot(layers[-1], self.weights[i]) + self.biases[i])
  ```
- **REQ-GRC-08 — Random initialization produces arrays of small values** [01:27–01:33, 02:28–02:37; f_0127_015]: Weights start random (frame shows printed numpy arrays with values ~±0.001–0.2); consequently the untrained softmax output is near-uniform (~0.1 per class in f_0230_034). Init transcribed from forward code (f_0659_084): `np.random.seed(0)`, weights `0.01 * np.random.randn(fan_in, fan_out)`, biases `np.zeros([1, output_size])`.

### D. Activations

- **REQ-GRC-09 — Linear-only network is useless (why non-linearity)** [01:43–02:00; f_0152_022, f_0155_023, f_0158_024]: Stacked linear layers collapse into ONE linear function ("no better than linear regression"). Demonstrated in a GeoGebra calculator: sliders m=-5, n=4.3, o=1, pq=1 composing into a single straight line `f: y = -5x + 4.3x + 1 - 5`; contrasted with a wavy sine-like dataset plot (f_0158_024) that a line can't fit.
- **REQ-GRC-10 — ReLU on hidden layers** [02:00–02:09; f_0200_025, f_0204_026/027, f_0213_031]: Add ReLU (rectified linear unit), `f(x)=max(0,x)`, plotted as flat 0 for x<0 and a linear ramp for x>0 (matplotlib plot, x∈[-10,8], y∈[0,9]). In the network drawing, the word "ReLU" is written vertically over EACH hidden column (f_0213_031 shows 3 hidden columns each labeled ReLU). Code (f_0659_084): `np.maximum(0, self.outputs[-1])`.
- **REQ-GRC-11 — Softmax on the output layer** [02:09–02:32; f_0215_032]: Final layer applies softmax to convert raw outputs into a probability distribution over classes (likelihood each class is correct). Formula shown on screen exactly:
  σ(z⃗)ᵢ = e^{zᵢ} / Σ_{j=1}^{K} e^{zⱼ}
  Numerically-stable code (f_0659_084): subtract the row max before exponentiating, then normalize by the row sum (axis=1, keepdims=True).
- **REQ-GRC-12 — Full forward pass code** [02:50–02:56 recap; f_0659_084, "Cell 17 of 47"]: Forward pass transcribed (condensed, faithful):
  ```python
  np.random.seed(0)
  self.weights.append(0.01 * np.random.randn(hidden_layers[len(hidden_layers)-1], output_size))
  self.biases.append(np.zeros([1, output_size]))

  def forward(self, inputs):
      self.outputs = [inputs]
      self.outputsTesting = ["inputs"]
      for i in range(len(self.weights)):
          # Dot Product
          self.outputs.append(np.dot(self.outputs[-1], self.weights[i]) + self.biases[i])
          self.outputsTesting.append("dense")
          # Activation Functions (ReLU + SoftMax)
          if i == len(self.weights) - 1:
              finalOutput = np.exp(self.outputs[-1] - np.max(self.outputs[-1], axis=1, keepdims=True))
              finalOutput = finalOutput / np.sum(finalOutput, axis=1, keepdims=True)
              self.outputs.append(finalOutput)
              self.outputsTesting.append("softmax")
          else:
              self.outputs.append(np.maximum(0, self.outputs[-1]))
              self.outputsTesting.append("relu")
      return self.outputs[-1]
  ```
  Note the bookkeeping pattern: `self.outputs` keeps EVERY intermediate layer activation (inputs, dense, relu, …, softmax) for later use in backprop, and `self.outputsTesting` records each layer's type tag as a string.

### E. Forward-pass validation trick

- **REQ-GRC-13 — Validate forward pass with externally trained weights** [02:37–03:00; f_0230_034, f_0243_038]: Before writing backprop, train the SAME architecture in PyTorch, export `model.state_dict()` (frame shows OrderedDict with `layer_stack.1.weight`, `layer_stack.3.bias`, …), load those weights/biases into the numpy network, and verify it reproduces high accuracy — **97.53%**. Notebook `neuralMNIST.ipynb`, section "Get Weights from PyTorch Model", `modelMNIST = Ne...layers=[256]` (hidden layer of 256). This isolates forward-pass correctness from learning-code correctness.

### F. Loss, backprop, optimizer (audio-only span, no frames 3:00–6:45)

- **REQ-GRC-14 — Categorical cross-entropy loss** [03:00–03:22, 04:17–04:28]: A loss function that "calculates how wrong our prediction was"; used as the error signal for backprop (class name in training code: `LossCategoricalCrossEntropy`, f_0709_087).
- **REQ-GRC-15 — Training cycle recap** [03:16–03:33, 05:00–05:11]: The loop is explicitly: forward pass → calculate loss → backward pass → update weights; repeat "enough times" and the network gets better.
- **REQ-GRC-16 — Backpropagation via partial derivatives** [03:33–03:55]: Update rule needs, per weight, "how much each weight contributes to the output," computed with partial derivatives, going BACKWARDS through the network.
- **REQ-GRC-17 — Chef analogy (credit assignment)** [03:55–05:00]: Network = team of chefs, each responsible for one ingredient (weight); taste the dish (compute loss), walk backwards to find which chef added too much/too little (per-weight gradient), tell the salt chef to add less next time (weight update proportional to its contribution to the error).
- **REQ-GRC-18 — Learning rate** [05:21–05:42]: The amount parameters change per update. Too high ⇒ the network "stumbles all over the place." Desired behavior: big steps first, smaller steps near the solution.
- **REQ-GRC-19 — Optimizer = SGD, fancier ones consciously skipped** [05:42–06:03]: Optimizers vary the learning rate (fast first, slower later). Momentum, adaptive gradients (AdaGrad), RMSProp are name-checked but rejected: "we're happy with our little SGD optimizer."
- **REQ-GRC-20 — The one-line backprop bug** [06:03–06:24]: First training attempt learned nothing; 3 hours of debugging traced to one line — calling `myNeuralNetwork.backwards(y)` when it should be `myNeuralNetwork.backwards(output)` (per audio: "my neural network that backwards why → my neural network backwards output"). Requirement: the backward pass must receive the network's forward OUTPUT (with the true labels available), not the labels alone.
- **REQ-GRC-21 — Diagnose training with loss/accuracy plots** [06:24–07:08; f_0645_082, f_0650_083, f_0705_085/086]: Plot loss (blue) and accuracy (orange) vs training step. Broken run (f_0645_082): loss spikes GROW over 30,000 steps while accuracy stalls ("weird plots"). Fixed via a 4-hour sweep of learning rates + different weight initializations + forward-pass re-review. Correct run (f_0705_085): loss decays from ~2.3 toward 0 and accuracy climbs to ~1.0 within ~175 plotted points. Sanity-check on small sample data BEFORE real datasets.

### G. MNIST application

- **REQ-GRC-22 — MNIST dataset spec** [07:08–07:31; f_0711_088, f_0715_089]: 60,000 images of handwritten digits, 28×28 pixels, 10 classes; goal is digit recognition.
- **REQ-GRC-23 — Input flattening** [f_0709_087]: Images reshaped for the dense net: `data = data.reshape(60000, 784)` — 28×28 → 784-length vector per sample (matches input column in diagrams).
- **REQ-GRC-24 — Mini-batch training loop** [07:31–07:47; f_0709_087]: First training gave 40–50% accuracy; parameter tweaks + mini-batches raised it to **97.42% on the test set**. Training loop transcribed (condensed):
  ```python
  accuracies = []; losses = []
  BATCH_SIZE = ...          # value not legible in frame
  # Main training loop
  for epoch in range(1, 10):
      print(f"epoch: {epoch}")
      train_steps = len(data) // BATCH_SIZE
      for step in range(train_steps):
          batch_X = data[step*BATCH_SIZE:(step+1)*BATCH_SIZE]
          batch_y = labels[step*BATCH_SIZE:(step+1)*BATCH_SIZE]
          X = batch_X; y = batch_y
          output = myNeuralNet.forward(X)
          if step % 100 == 0:
              predictions = np.argmax(output, axis=1)
              if len(y.shape) == 2:
                  y = np.argmax(y, axis=1)
              accuracy = np.mean(predictions == y)
              loss = LossCategoricalCrossEntropy...(...)
              accuracies.append(accuracy); losses.append(loss)
              print(...)
  ```
- **REQ-GRC-25 — Interactive inference on hand-drawn digits** [07:48–08:13; f_0748_097…f_0806_105, f_0016_007]: Draw a digit, `np.imshow(X.reshape(28, 28))`, `prediction = np.argmax(output, axis=1)`, `print(f"Prediction: {prediction}")`. Shown outputs: a drawn 9 → `Prediction: [9]` with probability **9.99919189e-01** highlighted in the probability vector; a 5 → 99.99%; a sloppy 7/5 → still 98.88% confident. Full probability vectors are printed alongside the argmax.
- **REQ-GRC-26 — Misclassification gallery** [08:07–08:19; f_0817_108]: Wrote code to display the test images the model got wrong as a grid of tiles, each captioned `True: X, Pred: Y` — used to confirm errors are "understandable" (genuinely ambiguous handwriting).
- **REQ-GRC-27 — Hyperparameter notes cell** [f_0809_106]: A markdown "Notes" cell in the notebook records experiment settings/results per run (text too small to transcribe; existence and practice of logging runs is the requirement).

### H. Fashion-MNIST generalization

- **REQ-GRC-28 — Same code, new dataset** [08:19–08:50; f_0833_110, f_0835_111]: Fashion-MNIST = same format (10 classes, 60,000 28×28 images) but clothing (sneakers, bags, ankle boots, pullovers…). The MNIST network code is literally copy-pasted unchanged and retrained → **87% accuracy**. Requirement: the implementation must be dataset-agnostic for any 784-in/10-out problem.
- **REQ-GRC-29 — Fashion inference demos** [08:50–09:05; f_0856_113, f_0858_115, f_0900_116, f_0904_119]: Bag → Label: 8, Prediction: [8] (p≈0.9997); trousers → Label: 1, Prediction: [1]; pullover/jumper → Label: 2, Prediction: [2]; plus a `True/Pred` misclassification grid (f_0904_119) where errors are again visually ambiguous items.

## Open questions

1. Frames 040–081 (3:00–6:45) were not extracted: the backprop implementation code (`def backwards(self, y_true)…` starts at the bottom of f_0659_084 but is cut off), the cross-entropy loss code, the SGD update code, and the exact buggy line of code were never visible — audio only.
2. `BATCH_SIZE` value, learning-rate value, and epoch count actually used for the 97.42% run are not legible in any frame (loop shows `range(1, 10)` → 9 epochs, but hyperparameters cell f_0809_106 is unreadable).
3. Exact hidden-layer sizes of the final MNIST net: PyTorch validation frame suggests `layers=[256]` (single 256-unit hidden layer), but diagrams draw 2–5 hidden columns — the drawn column counts are illustrative, not confirmed architecture.
4. Whether labels were one-hot or sparse: the loop handles both (`if len(y.shape) == 2: y = np.argmax(...)`), but the training encoding isn't stated.
5. The exact form of the cross-entropy + softmax combined gradient (whether he used the simplified softmax-CE derivative) is never shown.
