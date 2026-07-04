# Transcript

language: en (p=0.78)

[00:00] So machine learning and AI has taken over different aspects of our lives and it has also taken
[00:05] influence in many decision-making fields including trading and investing. So today what we're going
[00:10] to do is we are going to discuss about neural networks trading and how we can create efficient
[00:14] strategies like this which can beat the S&P 500 buy and hold returns and pretty much create your
[00:21] own strategies using neural networks trading or even improve on your existing strategies by
[00:28] adding a little bit of machine learning and AI. So let's start with what a neural
[00:32] networks trading is. So before that this is our third video in this series in our YouTube channel.
[00:38] So a few weeks ago we discussed about decision-free models and then a few months ago we discussed
[00:44] about the regression as well. So this is kind of complicated that's why I'm kind of delayed it
[00:48] this much because neural networks is kind of a complicated aspect for anybody to understand
[00:53] and learn. So I'll try to make it as simple as possible so you guys can understand it.
[00:58] So neural networks are just like the way your brain functions so it's like your brain has got
[01:02] neurons so when you see a number like three the brain looks at the number three identifies
[01:08] the curves and everything passed on the signals and makes a decision saying that hey it's three.
[01:12] So that's pretty much what neural networks does the machine learning model does so when you
[01:17] get an image of a cat then neural networks can identify that it's a cat through different kind
[01:21] of a training regime. So there are different kinds of neural networks the most basic one is a feed
[01:26] forward neural network so that's useful like image classification. So let's do this example here so
[01:32] let's assume that you feed in a measure of a cat and what happens is that there is the input layer
[01:38] which is the cat picture and then there are like hidden layers and each hidden layer will have
[01:44] certain information certain weights added to it so that weights will be initially set that's
[01:49] kind of like random weights and then it will identify it as something so let's assume that
[01:54] the initial identification is like a cheetah so obviously there's an error because this is not a
[01:58] cheetah this is a cat so it creates kind of like an error term like height and then it goes back
[02:04] into that weight area and then it kind of adjusts the weights so the different weights are
[02:08] weights here the weights there so the weights everywhere and each weight is going to adjust and
[02:13] then it's going to go forward again and then find out whether it's a cat or a mouse or a cheetah and
[02:20] again if there's another error then again it creates a new error and then again it goes back
[02:25] and does the whole process over and over again unless and until it finally gets the fact that
[02:30] it's a cat and then you've got really a neural network model here so what I just said right
[02:38] now is basically a simple example of a feed forward neural network so the initial things here
[02:44] those are the input input layers so I'm just going to mark it as i and then this is the hidden layer
[02:50] and then finally that is the output layer here so you've got the input layer hidden layer and
[02:55] output layer so you know the number of times this process goes over and over again that's
[03:00] called iterations or in other words epochs so in this example we have just taken a cat and then
[03:08] a picture of a cat and finally concluded that hey this is a cat and this whole model is called
[03:14] feed forward neural network now on the other hand in case of a recurring neural network
[03:19] we've got a different thing so this one doesn't have a memory so once the model is created it's
[03:24] kind of identifies that a cat with a cat so on the other hand when it comes to stocks or like
[03:29] for example predicting the next word you have essentially what is called recurring neural
[03:34] networks so recurring neural networks fundamental advantage is that it's got a memory advantage
[03:38] you can't remember things so for example it's used in a sequence of data like for example stock
[03:44] data so we'll say that's got prices of yesterday before yesterday and all those things so you've
[03:48] got like a sequence or like a sentence like I like to drink coffee so we can use that to predict
[03:56] the word here coffee I like to drink coffee so the thing that we said when I go back from the
[04:03] cat after the error and check back the weights that's called back propagation and then after that
[04:07] when it goes forward it is called forward propagation so there's a created a simple
[04:15] picture here got online so here you can see the back propagation so
[04:19] first initially it goes to the input units and it adjusts the weight of the hidden layers
[04:24] here these are the hidden layers in units one hidden units two so here we've actually
[04:27] created a simple one we just one hidden layer and here you can see there are multiple hidden
[04:32] layers there's two hidden layers and finally create the output and then the output goes back to create
[04:36] the error term and then adjust the weight from the hidden and the input and then it goes back again
[04:42] so that's called back propagation and forward pass so the difference fundamental difference
[04:47] between recurring neural network and the normal feed forward neural network it's got back
[04:51] propagation not only through the hidden layers but it's called back propagation through time
[04:57] so that's through the hidden state so it's got like a sequential time step so let's take this example
[05:02] of I like to drink coffee so in time t1 the first word you get is I and there's no previous hidden
[05:09] state and the current hidden state in this new hidden state created and that's h1 and then
[05:13] during the next time step you have got the word like and you've got a previous hidden state h1
[05:19] and then you've got a current hidden state h2 so it has got information from the previous
[05:23] hidden state as well so that's how it has gotten memory and then in time three t3 we've got two
[05:30] and then we've got the previous hidden state of h2 and then it got a new current hidden
[05:34] state of h3 so again it is carrying over that memory which the previous situation the cat
[05:39] didn't have so in this case because of the back propagation through time the recurring neural
[05:44] network has got an advantage and that is a whole idea of memory advance and finally in c5 we
[05:49] don't have any more input words and we've got the hidden state of the previous on h4 and
[05:54] based on that h4 state we make a prediction that it is coffee so just like the prediction is done
[06:01] for coffee you can actually use it to predict the stock price there so instead of t1 I like
[06:08] to drink it can be price of yesterday price of day before yesterday and things like that and
[06:12] you can use different kinds of input instead of the price you can use the RSI you can use
[06:16] volume and you can use the target as a fifth day return so here's like one two three four
[06:20] five the fifth word right into the fifth word you can actually use the target return as the
[06:24] fifth day's return so I've given like a trading example here so here we've got the time t1
[06:30] t2 t3 t4 t5 so input will be given the price of the first day and the RSI of the first day
[06:36] the price of second day and RSI of the second day so each time in the hidden state the memory
[06:41] is being stored and the new information is carried over and that helps us to predict certain things
[06:48] in the stock market we can predict that the market is going to be a positive or a negative by using
[06:53] all the RSI data and the price data across the past so the recurring neural network or fundamental
[06:59] neural network has got certain problems the fundamental problem is that it's got a computational
[07:05] issue so we need lots of computational power unlike decision tree or regression where we can
[07:09] actually create so in our strategy we actually use QuantConnect and they don't use GPUs, they use CPUs
[07:15] and still we were able to create one but when we go to more complex one like LSDF it takes a long
[07:21] time to test it so even in QuantConnect I've seen like 15, 20, 30 minutes for it to actually load
[07:27] up and there's a time after the certain time it kind of shuts down because you know it's too
[07:31] much load for the computer to actually run the strategy but even then QuantConnect is pretty
[07:37] good in executing these machine learning models but in future what is going to happen is that
[07:42] you're going to have GPUs and everything to make the models even more powerful so in this specific
[07:47] strategy we created a 64 as the memory vector so we can also decide on how much the memory
[07:52] vectors are so we can create more complicated memory vectors like from 64 to 128 to 256
[07:59] so in the strategy we use 64 so it's much more faster to train the model and then we can do lots
[08:05] of kind of hyperparameter tuning we can we can change input features we can change the epochs
[08:11] that's the number of iterations that the model used to train you can use the hidden exercise
[08:15] that's what I've said here and you can also adjust things like learning rate so these are all like
[08:20] more complicated hyperparameter tuning which I'm not going to explain it here but I have
[08:24] explained it thoroughly in our course so this basically is covered in our machine learning
[08:31] and AI course including this strategy so we've actually got eight machine learning and AI
[08:36] strategies we have also got combined machine learning strategies where they combine
[08:40] recurrent neural networks without a regression and things like that so that's
[08:43] give us a fundamentally better edge so we've used AI in even portfolio rebalancing
[08:50] also in combining multiple models and after each section each model that we discussed
[08:56] basically we've discussed five models here we've discussed regression
[09:01] decision tree support vector machines recurrent neural networks and long shorter memory and
[09:06] after each of these sections we've got a strategy and after each study we've got a quiz as well so
[09:10] a quiz would be something like this so for example this is a recurrent neural network
[09:15] quiz so this quiz is a create so that you understood what's being explained so that you
[09:20] can create your own recurrent neural network strategy and you have a strategy code in the
[09:25] lecture and all those things so we've also got different kind of strategies as well
[09:30] all these strategies have beaten the SPX CAGR to maximum drawdown ratio that's what we are aiming for
[09:35] in our course or any strategy when you create the fundamental comparison measure is the SPX
[09:41] CAGR to maximum drawdown ratio so we also discussed the applied Markowitz portfolio to my
[09:45] favorite way as well so coming back to this lecture so one of the advantages of the neural
[09:52] networks we can we can apply to anyway so imagine you have like a strategy which is performing well
[09:56] you can actually make it perform even better reduce the drawdowns and things like that using neural
[10:00] networks so going back to the recording neural networks RNN has got a fundamental problem
[10:06] and that is the vanishing gradient problem so it tends to forget stuff that is kind of like in the
[10:11] past so for example when you read a book that's how you're reading Stephen King's The Stunt which
[10:15] is like really really big so you tend to forget some of the characters because there are lots
[10:19] of characters so just like human beings we forget stuff so the neural networks also tend to forget
[10:24] stuff and that's because of the back propagation errors and the weights and things like that
[10:28] so in order to avoid the situation LSTM has got a thing called forget gate so along with the
[10:34] hidden units there will be a forget gate which kind of takes care of the problem of the
[10:38] things that they forget and it will take in different situations the important things
[10:42] in the past that has to be remembered so that helps us improve our results for the LSTM
[10:46] but the problem with LSTM fundamentally is that it is extremely computationally intensive that it
[10:53] will take a while to back test this strategy in LSTM so let me get the LSTM strategy here
[11:04] this is the strategy we did for the LSTM we've done the portfolio optimization rebalancing
[11:11] using the LSTM machine learning model AI so these machine learning model AIs
[11:16] like neural networks not only for you to create efficient strategies it can also be to rebalance
[11:22] a portfolio if you imagine you have like a value investing portfolio and you need to adjust the
[11:26] allocation of the portfolio so you can use the machine learning model to actually allocate
[11:31] how much money do I need to allocate to SSY how much money do I need to allocate a GLD,
[11:35] SBIR, CLC and get superior returns while minimizing the drawdown so these are some
[11:40] of the things that machine learning models like R and LSTM and many other things can use it's
[11:44] just not for entry or exit conditions it can be to improve your existing basic
[11:48] one trading strategies it can also be to rebalance a portfolio so now let's go back
[11:54] and discuss the code of the recurrent neural network okay so as you can see I have imported
[12:01] the libraries NumPy and scikit-learn so there is a fundamental Python library for neural
[12:06] networks in LSTM but for this specific strategy for the R&M what I did is that I actually
[12:11] created the equations myself so that you guys can understand how the process is done
[12:17] and if you want to make any changes the advantage of having libraries is sometimes it can be
[12:21] you don't know what's happening inside but it is easy to use just have to import the libraries
[12:27] and actually run it but sometimes it's also good to know what happens inside of it so I actually
[12:32] created the code myself for the recurrent neural network so you've got the start is
[12:37] end so that will be a testing data set the cache I've taken values of RSI, MA and 200 so
[12:45] if you don't know anything about a QuantConnect or Python I think the first thing you could do is
[12:50] visit our YouTube channel and go through algorithmic trading in Python zero to hero
[12:55] and once you're done with that you can actually visit our QuantConnect possessorial as well so
[13:00] you kind of up speed on how to handle Python and then you can come here and it will be easy
[13:05] for you to understand so these are kind of like the prerequisites that you will need to understand
[13:09] the certain level of Python so you understand what the code does we're warming up the data so
[13:14] it warms up 200 days and then we are looking into the parameters we are looking into how many
[13:19] days we need to look back remember we did t1, t2, t3, c4, and t5 so that could be like five
[13:25] lookback periods so in this case we're doing 10 lookback periods we are doing a feature account
[13:31] so that could be anything could be a price change it could be an overnight gap it could be
[13:34] a volume change it could be an RSI it could be anything so it's kind of up to you on what to
[13:39] choose the input features are we are not going to show the input features that we have and the
[13:43] end view exit conditions that we have but for the people who have done the course you have access
[13:47] to that specific thing so you've got the hidden site so remember I said the 64 128 128 the
[13:54] vector sizes the memory vectors so that's kind of dictated here then the learning rate is
[14:00] dictated and then initially the prediction is set as zero because that's what we're going to find
[14:04] the value is the prediction going to be positive or negative to go long or short we've used the
[14:08] standard scalar to scale our numbers of people who don't know standard scalar so basically we
[14:14] make a different data so for example RSI can give you a certain number volume can give you like 100
[14:18] thousand so the RSI might be like 30 or something so you see all these complete variations of these
[14:24] numbers so in order to make those numbers kind of be comparative that's why we use standard
[14:29] scalar the standard scalar helps us convert these numbers to analytical ones so that there is no
[14:35] massive discrepancy because a bigger number can affect the model completely so we don't want that
[14:39] kind of a choice the volume might take over instead of the RSI number so you know what to do
[14:44] that is why we use standard scalar and then we're going to use initialize RSI function which
[14:48] is something that I created and also the train RSI function so the initial ones are the ones
[14:53] that we decide on the weight and then we also decide the biases so initially as I said before
[14:59] the weights I think I did said before so initially the weights are set as random the first
[15:06] first time it goes and then when you get the errors and the weights are adjusted accordingly
[15:11] so in this case you've actually set up the random function and created the
[15:16] weights and also we create the bytes and then finally we train the models but training
[15:20] we're using 2000 to 2009 so I've discussed this in our previous video videos about
[15:25] training and testing data so we're using training data in 2000 to 2009 and we are testing it
[15:30] on 2010 to 2020 but you can change this you can update it as you keep on going
[15:37] you can actually do it from I don't know 1990 to 2000 and then train that on I mean test that
[15:43] on 2010 instead as well and then we're going to get an array which stores the features and the
[15:48] targets and the features are going to be caused by my get features from history
[15:54] where we can feed in the input features whatever input features you want and then obviously there's
[15:58] a target and then obviously we're going to scale up it the features and then we're going to transform
[16:06] the features and here is the epochs of the iterations the amount of iterations of which
[16:11] again increases iterations to higher number but again it is going to come with a higher
[16:15] computational power and sometimes quantum connect may not be able to handle it if
[16:19] you give in like too many epochs and then we're going to find the epoch losses and all those things and
[16:25] here is the forward propagation and also the backward propagation as well so here you can see
[16:33] we have used the self dot backward function here to find out the epoch loss and the hidden
[16:38] states and targets and the prediction and then here is the forward propagation we've
[16:43] got the hidden states here it's an empty array and then we attend the hidden states we add up
[16:48] the hidden states and we can see here we have actually put in the weights and also the biases
[16:54] and we have a return y and also the hidden states as well and then with that information of the
[17:01] hidden states and the y and y underscore credit is the value that we are trying to predict we feed
[17:06] in the weights and then we do the backward propagation and we get the biases and weights
[17:13] and then we keep on updating it because it's gone through different kinds of epochs right so
[17:17] we've got the learning rate again it's been adjusted so finally we have got the completely
[17:22] complete model of the backward propagation so we've got the backward propagation and we've
[17:28] got the forward propagation and it's been great and then comes the depth on data which I'm not
[17:32] going to go too far because that's basically the entry and exit conditions and also the
[17:39] features the input features as well so those are available for our members and they can access
[17:45] it in their specific strategy code section let's go through the results of this and see how it has
[17:52] performed okay so we have actually included the commissions as well so all our strategies come
[17:57] with commissions included so let's go to the strategy the strategy is performed on the SPY
[18:02] as you know as it seems in the code so we've got a compounding and a return of 9% with the drawdown
[18:07] of 18% so let's do the calculation so the S&P 500 CAGR to drawdown ratio CAGR is 10
[18:15] and we are dividing it by the drawdown maximum drawdown which happened in the 2008 financial crisis
[18:21] that's 55 so we've got a ratio of 0.18 so unless you've got a strategy which is above that
[18:26] we can't go ahead in executing that strategy so in this case it's 9% divided by 18.3 so we've
[18:36] got a ratio of 0.49 which is pretty impressive so the S&P 500 buy and hold CAGR to drawdown was 0.18
[18:45] so the advantage of this is we can apply a little bit of leverage you can apply like a two is two
[18:49] and leverage and get like an 18% CAGR and still the drawdown will be just like 36% or something
[18:55] like that still it won't be the maximum drawdown of an S&P 500 buy and hold so there are lots
[19:01] of things we can adjust to it in these numbers and we can make the strategy improve by adjusting the
[19:11] epochs or adjusting the input features or changing the input features or adjusting the hidden size
[19:16] and things like that so there are lots of things that we can play around with in the input features
[19:22] or the hyperparametric which we have explained thoroughly in the course and that is one
[19:25] of the challenges that you have like we give you a condition these are things that you have to
[19:28] change and these are the things that you can improve the strategy so this is the R&M strategy
[19:33] you can actually improve this strategy as well by combining it with different models so
[19:38] let me go through some of the performance of our machine learning strategy of the
[19:42] training data so I can see different models yes S&P 500 ratio is 0.18 so our linear regression
[19:48] model has 0.32 decision 3.45 support vector machine 0.44 recording your work 0.49 there's
[19:57] combined model of 0.39 there is the combined AM model 0.45 there's another decision 3 of 0.41
[20:04] I think I even put in the LSTM so I think it might be there below here long short term memory
[20:14] there you go that's a long shorter memory that also has done spectacularly well then we have got
[20:18] the RNN regression which is combining the RNN and the regression we also got the RNN plus
[20:24] support vector machines as well so there's lots of growth prospects when it comes to
[20:30] application of machine learning and AI to training and these are just the fundamentals we are just
[20:34] taking baby steps so I think within like a two to three years time frame people will be deciding
[20:39] more about what kind of machine learning models to apply for a specific training strategy can
[20:44] we apply it on a momentum training strategy how can we change the portfolio how can we create
[20:49] multiple strategies using neural networks can we apply neural networks on multiple
[20:55] quantitative training strategies to rebound the portfolio so the amount of growth prospects
[20:59] for this is very huge so hope you guys enjoyed the video let me know you understood everything
[21:06] let me know if you have any confusion in any of these things I'll be happy to help you thanks
[21:10] for watching bye bye
