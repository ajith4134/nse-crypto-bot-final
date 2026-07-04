# Transcript

language: en (p=1.00)

[00:00] I built a neural network that trades stocks. It was consistently profitable for the last five years,
[00:04] even when the market was bleeding in 2022. The way it works is that on every bar,
[00:07] I take a 64 by 12 feature window and run it through a causal temporal convolutional network.
[00:11] That embedding turns into the next bar probability, but the real secret sauce comes from a proprietary
[00:15] risk map I developed. I applied a neutral zone dead band, scaled the signal inversely with
[00:19] forecast volatility, and then capped exposure. I still have a lot to learn, but I'm pretty
[00:22] happy with this so far.
