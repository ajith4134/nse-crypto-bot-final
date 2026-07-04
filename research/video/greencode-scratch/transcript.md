# Transcript

language: en (p=1.00)

[00:00] This is a neural network and today I'm gonna build it from scratch. That means no machine learning
[00:05] libraries, no pre-built frameworks, only numpy, python and some maths. We're gonna go from
[00:10] individual neurons to more complex networks and finally I'll test if my creation can learn the
[00:15] numbers and if it has a fashion sense. Let's start by coding a single neuron. Imagine a neuron
[00:21] that has three inputs and one output and this output is the weighted sum of the inputs.
[00:26] Wait wait wait what do you mean by weighted sum?
[00:28] Well each of these connections has a weight and to get the output we multiply them by their inputs
[00:34] and add a bias. We sum it all up and that's the output. Now how do neural networks learn?
[00:40] Well by tweaking the weights and the bias to get the output we want but we'll get to that.
[00:45] Okay that's all good and fun but a single neuron is pretty boring. How does a network with more
[00:50] neurons look like? Well it looks like this. Yeah I also shot my pants the first time I saw this
[00:56] but if you actually visualize this it looks like this. All the neurons are interconnected with each
[01:01] other. All these connections mean that the output value of this neuron is calculated as the weighted
[01:06] sum of all the previous ones and the same thing happens on the next layer and so on and so on
[01:11] until you get to the final output and you might be asking well if we have to calculate all these
[01:16] little connections we're gonna be here all day and you're right that's what we have linear
[01:22] algebra. Basically many many years ago some of these guys invented the dot product which converts
[01:28] all this mambo jumbo into this one python line. Pretty convenient huh? Okay let's code this real
[01:33] quick and boom we have some output values let's go and this is all very pretty good you can
[01:38] definitely train it and use it for some cool stuff but if you excuse me I'll have a 20 second
[01:43] math explanation of why this isn't good enough. Ready? All right start the clock. So now we have
[01:48] all these neurons that multiply each other to produce a value but if you really really really
[01:52] think about it this is just a linear function with a bunch of parameters we don't want that
[01:56] because it's no better than linear regression we want to introduce some non-linearity and we do
[02:00] that with ReLU which stands for rectified linear unit it looks like this and if we add it to the
[02:05] network it will be better at understanding non-linear data just trust me on this one but
[02:09] are you sure you know what you're doing just trust me. Finally we slap a softmax activation
[02:14] function this is one of those functions that looks really scary but it just converts a bunch of
[02:19] weird numbers that the network outputs into a probability distribution which is just a
[02:23] scary way of saying that it tells you what the network thinks is the likelihood of each
[02:28] class being the correct one and as you see we're getting a pretty random probability
[02:32] distribution which makes sense because the weights and biases are all random and here's
[02:37] when I had a 500 acu moment you'll see I'm a genius what I did is I trained this exact same
[02:43] network on PyTorch got the correct weights popped them into our network and boom we got 97.53% accuracy
[02:50] all right that's it video's over nah just kidding now we have implemented all the forward
[02:56] paths from scratch and we know it works because we tested it with trained weights now comes a
[03:00] difficult part teaching the network to actually learn but before we actually do that we need
[03:05] a way to calculate how wrong the network is for that we use cross categorical entropy loss
[03:10] which is more maths that I can really be bothered to explain right now all you gotta know is that it
[03:16] calculates how wrong our prediction was that's it plain and simple okay little recap we input an image
[03:22] or whatever the network does it's networking with value and linear layers we get an output
[03:27] we calculate how wrong the network was and now we need a way to update the weights and biases
[03:33] so that the model actually learns something this is what's called back propagation spoilers
[03:39] it's more math but we're gonna pretend it's not and explain it in simpler terms now we know
[03:44] how wrong our model is but we can also calculate how much each weight contributes to the output
[03:50] and this is done through partial derivatives hey I said no maths dude get this get this out of
[03:55] here come on go away go away okay let's break it down imagine our neural network as a team of
[04:01] chefs working to create a dish its chef is responsible for a specific ingredient
[04:06] and the taste of the dish the output depends on how well each ingredient is balanced if the dish
[04:11] test is off we need to figure out which chef added too much or too little of their ingredient
[04:17] and here's where back propagation comes in first we need to taste the actual dish in our case we
[04:22] calculate the loss or the error using the cross categorical entropy loss function this tells us
[04:28] how off is the taste from what we want now we need to adjust the amounts each chef is adding
[04:33] to get closer to the perfect taste to do this we go backwards through the network and figure out
[04:38] how much each weight the chef's contributions need to change to reduce the loss it's like tasting
[04:44] the dish realizing it's too salty and telling the chef responsible for the salt to add less
[04:49] next time and finally once we know how much each chef contributed to the final dish we tweak
[04:55] their ingredient amounts their weights based on the feedback they get until the dish taste is just
[05:00] right so forward pass calculate the loss backwards pass update the weights forward pass calculate the
[05:06] loss backwards pass update the weights and if we do this enough times eventually the network just
[05:11] gets better okay so implementing this took me way longer than the forward pass but i'm gonna
[05:16] pretend it was really easy and it only took me half an hour instead of five hours and here's
[05:21] something i didn't tell you the amount the network changes its parameters is called the learning
[05:26] rate so the higher this number is the more rapidly the network is going to change its parameters well
[05:31] why don't we put it super high so it learns super fast well if we do that then the network is going
[05:37] to stumble all over the place we don't want that we want to take big steps at first and then smaller
[05:42] and smaller steps once we get closer to the solution and this is where optimizers come in
[05:48] they bury the learning rates so that the networks learn fast at first and then slower
[05:52] and slower you can also do a bunch of fancy with them like implementing momentum adaptive
[05:57] gradients root mean squared propagation we don't really need that we're happy with our little
[06:03] sgd optimizer so after i implemented back propagation my network was not learning like
[06:08] at all it was misclassifying a bunch of data and it was basically completely useless so i spent
[06:13] three hours debugging it only to realize that i had made a mistake in this one light of code
[06:18] instead of my neural network that backwards why it should be my neural network backwards output
[06:24] i love it when that happens and after fixing that i also started getting some weird ass looking plots
[06:30] yeah i know is this absurd art or what it looks kind of cool so i decided to turn it into a
[06:35] t-shirt go buy it at www.weirdplots-t-shirt.com we only have 10 000 stocks so go buy it before
[06:42] somebody else does just kidding just kidding not doing merches yet anyway i got this weird plot
[06:47] when training on some sample data and just for reference it's supposed to look like this this
[06:52] sent me into a four-hour rabbit hole of trying different learning rates initializing the weights
[06:56] differently and i even started second guessing my beautiful forward passcode and after fixing a
[07:02] bunch of stuff bug after bug after bug i finally got this it's not perfect but it's definitely
[07:08] less weird and with my new fund confidence on my code i decided to tackle the mness dataset
[07:14] i have already done a video about this but the mness dataset is a collection of 60 000 28 by 28
[07:20] pixels of hundred digits and with it you can teach a neural net to recognize a hundred the number
[07:25] like if i draw this eight real quick and pass it through the network boom it notes it's an eight
[07:31] this might look kind of simple but honestly i think it's pretty cool at first after training my
[07:35] neural net it had horrible accuracy i'm talking 40 50 percent but after tweaking some parameters
[07:41] and implementing mini batches i got up to 97.42 accuracy on the test set pretty sick right so let's
[07:48] test it out okay let's see what he thinks of this okay he predicted a nine nice okay let's try a
[07:53] different nine wow he's 99.99% sure that this is a nine lowkey it's getting kind of cocky so what about
[08:00] this five again 99.99% confidence that this is a five okay let's find a more challenging one
[08:07] wow still 98.88% sure even though it looks like a two-year-old do this so i wrote some code to see
[08:13] what the model got wrong and i gotta say it's pretty understandable i mean come on who did this
[08:19] now some people say that training on normal mness is too easy that's why they created fashion
[08:26] mness it's the same concept as mness there are 10 classes and 60 000 images but instead of numbers
[08:31] boom we have pens we have sneakers bags uncle boots let's train it on this data set and see if our
[08:37] neural network has some fashion sense okay training training training and boom 87 accuracy not bad
[08:45] huh not gonna lie i feel like it could do better but i literally copy pasted the same neural net
[08:50] code from mness and got 87 percent so i'm happy with that let's see what this puppy can do okay
[08:56] let's see what he thinks of this bag nice what about these pens what about this jumper now
[09:01] this guy's good and again the stuff it got wrong was pretty understandable and there you have it from
[09:05] individual neurons layers of neurons to actually doing some pretty cool stuff hope you enjoyed this
[09:10] video and subscribe i got some cool stuff coming in the next couple of weeks see ya
