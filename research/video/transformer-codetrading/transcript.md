# Transcript

language: en (p=1.00)

[00:00] Hi, and welcome back.
[00:02] In this video, we will be using artificial intelligence models to generate future trading
[00:07] forecasts.
[00:08] Large language models like chat GPT use a powerful architecture called the transformer
[00:14] to predict the next word in a sentence.
[00:17] That's how they generate such a human-like text.
[00:19] More precisely, if we provide a sequence of words, the model will look for the most
[00:25] probable words that can complete this sequence.
[00:28] But what if we apply that same technology to financial markets?
[00:32] Instead of predicting the next word, we predict the next price or trend.
[00:36] And that's what we will be exploring in this video.
[00:39] We will walk through setting up a transformer model in Python using PyTorch,
[00:44] training it on historical price data of the Euro-US dollar,
[00:47] and using it to predict future price movements.
[00:49] So you will see how we can adapt the same techniques that power large language
[00:54] models like chat GPT to our own trading and investing strategies.
[00:58] I'm also sharing the Python code I'll be using today in a link in the description
[01:02] of the video so you can download it, run your own experiment and see how these models work.
[01:07] Transformers first exploded in popularity for natural language processing tasks.
[01:12] Let's imagine you're using a model like chat GPT, you type in a prompt,
[01:17] and it responds by predicting the most probable sequence of words.
[01:21] In the background, transformers are analyzing all the words or tokens in your prompt,
[01:26] building something called attention matrices that determine which parts of the prompt
[01:31] are most important, and then generating the best possible continuation of your text.
[01:36] This attention mechanism is the key innovation.
[01:39] A transformer uses several heads or matrices, each looking at different relationships in the sequence.
[01:47] Think about a head as a matrix of parameters providing the importance, value or weight of each
[01:53] word. If we're talking about text, one attention head might look for example at how nouns connect
[01:59] to verbs, while another head could track pronouns referencing earlier subjects and so on.
[02:06] By splitting attention across multiple heads, which are basically matrices,
[02:11] the model can track a wide variety of relationships simultaneously.
[02:16] Now, why is that relevant for time series predictions like forex or stock prices?
[02:22] Well, price data is also a sequence, just like text, but instead of words, we have candle values
[02:28] over time. In theory, a transformer can be adapted so that instead of predicting the next word,
[02:34] it predicts the next price or a range of future prices. The same concept of attention applies.
[02:41] Each time step in the sequence can learn how to weight the importance of previous time steps.
[02:47] In other words, the model learns which past price movements are most relevant for forecasting the
[02:53] future. In practical terms, we will feed our past prices and any technical indicators into the
[03:00] transformer. The model will look across these historical windows and figure out which
[03:05] signals matter most. Then it outputs the most probable next price or price sequence,
[03:11] similarly to how chat GPT picks up the most likely next words. Results can vary depending on hyper
[03:17] parameters, data quality and market conditions, but there's no doubt that transformers represent
[03:23] a major leap forward for advanced sequence modeling. They can capture the long-term
[03:28] dependencies more effectively than older architectures like LSTMs or traditional
[03:33] recurrent neural networks. And I decided to try this on trading to try transformers on trading data
[03:40] and share it here on YouTube today. Now, let's jump into the code and see how these transformers
[03:46] work for trading applications. Grab your coffee, fire up your code editor and let's get started.
[03:52] So this is our Jupyter notebook. We will start by installing torch pandas, numpy,
[03:58] scikit-learn and TA or pandas TA for technical analysis, just to compute some technical indicators.
[04:05] Now we can start defining some functions that we'll be using later on in the program.
[04:09] So load forex data that takes a CSV file, it reads a CSV file, puts it into a data frame,
[04:17] cleaning and casting to date time format, the GMT time column. And then we're sorting
[04:23] the value by date, just in case, we're resetting the index and we return the data frame.
[04:30] Second function is adding technical indicators. It takes the data frame and it computes the RSI,
[04:36] olinger bands high and low, the moving average 20, and the moving average slope. So that's just
[04:43] the difference between the current moving average and the previous one, two different rows or two
[04:49] consecutive rows. We apply some cleaning, filling, missing values, and then we return the data frame
[04:56] with these technical indicators. Now, if you want to enhance this part, this is where you can add
[05:04] on your own indicators, maybe you want to add, I don't know, different moving averages with
[05:09] different length, the exponential moving average, or any other technical indicator
[05:14] that you want to include in your study, so that the transformer will read it and try to understand
[05:21] the data or the price movement based on these indicators. For this video, I just kept it simple,
[05:27] I'm using those two, so I'm using all three indicators, I'm using the RSI, bollinger bands,
[05:32] and the moving average. Now, this function, select and scale features will take the data frame
[05:39] and the names of the features or the columns we would like to include in our study.
[05:44] We're going to take by default the open, high, low, close, the RSI, bollinger band high, low,
[05:51] moving average 20, and moving average 20 slope. So that's the slope of the moving average.
[05:56] And then we're going to apply the minimum maximum scalar to these features, to these columns.
[06:02] We're going to apply the fit transform function with the scalar, the minimum maximum scalar
[06:08] on the data. So what this does actually, it will scale the values of these columns
[06:16] in between two boundaries, so that no column takes more importance or more weight.
[06:22] Then from torch, utils, data, we're going to import data set and data loader. And we're
[06:30] going to define a new class for its data set that inherits from data set. This is basically
[06:35] preparing the data so that it can be understood and read well by the transformer model.
[06:44] And these parameters actually are very important at this point. So the sequence length is by
[06:49] default is equal to 60. That's how many rows we're going to read the transformers going to
[06:54] read before trying to predict the next row. And then the prediction length is one. So we're
[07:00] going to predict one candle in the future, the feature dimension by default, it's equal to four,
[07:07] but it can be changed to nine, I think 123456789. So we have nine features at this point that we can
[07:15] choose to use part of these or all of these at the same time. And then the target column index
[07:22] is three, because we're going to target the closing price. So what we're going to predict
[07:27] is actually the closing price of the very next candle. We're just applying one candle in the future
[07:34] for prediction length. And then we're going to predict the closing price of that particular candle.
[07:40] And then that's it, actually, this is the data defined here. And we're going to
[07:46] define the x, the input. So that's the sequence that we're looking to the
[07:52] closing prices actually of the last 60 candles by default. So that's the x part. And the y part,
[07:59] the future price is the very next candle closing price. So we're going to put these as labels
[08:07] for the training, the model will be looking at x, but also at y values to learn and fit
[08:15] what kind of sequences will yield what kind of future price or closing prices.
[08:20] And then when we are validating or testing the model, we just provide the previous sequences,
[08:26] and then the model has to guess the future price. So for the training phase, though,
[08:30] we need to provide the labels. This is called supervised learning in machine learning.
[08:36] And notice the return format is a torch tensor. So we're not working with non pi
[08:42] arrays anymore. We're just using torch tensors, because this is what we will be
[08:46] providing for the transformer neural networks. Okay, and now we will define our transformer model.
[08:55] So the class is time series transformer, it inherits from neural networks dot module from torch. And
[09:03] these are the parameters of the transformer. So the feature size is nine. Remember, we have nine
[09:08] features by default. We have two hidden layers of neural networks, we have a demodel of 64,
[09:16] number of heads eight, the dimension of feet forward is 256. Now, if you have noticed that
[09:23] eight times eight is 64, 64 times four is 256. And they are all multiples of two,
[09:33] these are the rule of thumbs actually followed by data scientists and AI engineers while defining
[09:40] such kind of neural network architectures. Now there is no theory behind, there is no clear
[09:46] theory behind actually. But these are good values for this kind of study. Now we can increase one
[09:53] of these, but we would have to increase the others. It's not mandatory, but it is recommended.
[09:59] Then in order then in order to avoid overfitting, we have a drop out of 0.1 sequence length,
[10:05] I've shortened it to 30 here instead of 60 to make things a bit faster while training and using the
[10:11] model. And the prediction length is equal to one because we're predicting just one step ahead,
[10:17] not more than that. So we're going to predict just one value. Remember that
[10:23] in chat GPT, it can predict a sequence, which is a sentence. So you write five or six words and it's
[10:29] going to predict the next six or seven words. We're trying to predict only one future value
[10:36] here to make it as simple as possible. Now I'll not go through all the technical details here,
[10:42] but this is where our transformer is defined using PyTorch. So that's basically the encoder
[10:50] here with all the parameters. So the number of layers, the number of heads, the attention heads,
[10:54] and so on. Remember that we have mentioned the attention mechanism. And that was actually
[11:00] published by Google, I think with the paper entitled attention is all you need. And this is the
[11:06] architecture that was used by GPT, OpenAI, and so on and so on. So the number of heads is the
[11:13] number of attention heads. We're going to use eight or not more. So we could increase these again,
[11:20] just to check the relationships. Each head will focus on a relationship of the price,
[11:26] the current price, and the previous prices or a certain sequence of previous prices.
[11:32] What comes before is basically reshaping the data and preparing the input of the model.
[11:40] But then this is the model. And then we have the output of the model right here.
[11:46] Again, I'll not go through all these details. It might get boring as a YouTube video. But
[11:52] the architecture is summarized here for now as is. And we're going to use this part for our
[11:57] trading. Now, this is where we're going to train the transformer model to train the model
[12:03] actually is let it read the sequences of data, the closing prices with all the input features,
[12:10] the nine features, the RSI, the well-injured bands, moving average, the slope of the moving
[12:15] average, and so on. And also letting it read the future closing price, the next step,
[12:20] just one step ahead. Why? Because it's going to fit the parameters of the neural networks.
[12:26] It's going to learn from this data what kind of sequence and what to expect, what kind of sequences
[12:34] we could have and what kind of future values we could expect after these sequences. So in the
[12:41] future, whenever we have similar sequences or similar patterns, it's going to know how to
[12:47] predict what's the most probable next closing price. And this is where it's happening. It's
[12:53] in the train transformer model function. This function takes the model as a parameter,
[12:59] the value loader, the learning rate, 10 to minus three, number of epochs, how many times we're going
[13:05] to keep repeating for for the learning process, so 20. And now I'm training on the CPU. If you
[13:12] have a GPU, you might want to switch this to a GPU. But I've tried it on CPU, it's working on mine.
[13:19] So I'm not going to touch it for now. Now, after training the model, we're going to return the
[13:26] trained model. So that function is going to train the model on the data and it will it will return
[13:31] actually the model. And now we'd have to evaluate the model. So to evaluate the model, we need to
[13:39] provide the model, the trained model, the data. So providing test loader. So that's basically the
[13:47] data for for test for testing. Then we have the scalar, the featured columns, the target column,
[13:54] which is three, the index of the target column, which is three, because we're
[13:58] targeting the closing price, the window width, which is by default 10. So it could be 30 or
[14:05] 60, as you may have seen before, starting index zero, the prediction length is still one and
[14:12] the device is still the CPU. And this function is actually going to take the model, a new set of data,
[14:19] and it's going to provide the model with the length of sequence 30 or 60 rows, depending on how we've
[14:27] trained the model. And then it's going to ask the model to try to predict the very next value,
[14:33] the very next closing price, it's going to compare this price with the ground truth price,
[14:39] like what really happened and what the model predicted. And we're going to compare these together.
[14:45] So obviously it's going to give us some metrics, but mostly we're going to plot
[14:50] the predicted closing, closing prices and the real closing prices together.
[14:58] And now we have all the sets of functions that we'll be using actually to train and evaluate
[15:03] the model. So you don't have to understand all the details. I mean, it takes up a certain
[15:08] level of expertise. And to be familiar with artificial intelligence, machine learning, neural
[15:14] networks, especially transformers, actually, these are some kind of a recent architecture,
[15:19] it's working for now, you can copy and paste the functions. And this is where we're going to use
[15:24] the functions. So this is the cell where we call the functions, tune the parameters. And this is
[15:29] where you can apply your modifications as well. So I'm loading a euro US dollar candlesticks,
[15:36] one hour data between 2020 and 2023, it's a CSV file, I'm using the load forex data to load this
[15:44] file. And then I'm adding the technical indicators using the function. Now you can see how easy it is
[15:50] calling the functions, providing the data frame and returning a data frame with just the added and
[15:56] scaled technical indicators, actually, they are not scaled, we'll be scaling these in the next
[16:01] function, which is select and scale features data frame. So I left it by default, it's going to scale
[16:08] the nine features in the data frame, the target, then the target column index is equal to feature
[16:15] columns dot index of the column close. And we're going to use this later on. So then we have the
[16:22] sequence length is equal to 30. So I'm overriding all the default values that we've used before,
[16:29] prediction length is still one, we just want to make it as simple as possible, you might want to
[16:35] adjust it to three candles in the future or five candles in the future, but it's going to be
[16:40] a bit problematic to, to compare and to evaluate with the future values. Then we have the data
[16:48] set, we're going to use the forex data set that we've defined before. And we provide all the
[16:56] parameters, the required parameters that we have already, then we split the data into training
[17:02] size. So that's 80% of the CSV file, your US dollar that we have 10% for validation,
[17:10] and another 10% for the testing size. So we have our data, we're splitting the rows into 80% of
[17:19] these are going to be used to for the learning phase of the model. But then for the validation,
[17:26] we're going to check for 10% of these of the data. And then the last 10% are for the test size. So
[17:34] somehow we are letting the model learn on a big chunk of the data, but then we're testing it
[17:40] on another 10% and another 10% just to evaluate how the model would perform on new and unseen data
[17:48] during the training phase. Now I've left this line here on purpose, just don't do this.
[17:56] This is where we're going to split the data actually into 80%, 10%, 10%. But there are
[18:03] two ways of doing this either we slice these sequentially. So the first few rows are the
[18:09] 80%. So these are the training set, then the next is the validation, and then the next is the
[18:15] test. But by default, in machine learning, we have the habit of random splitting. It means like
[18:22] picking up 80%, randomly picking up 80% of the of the data points, and then randomly picking up
[18:29] another 10%, and then another 10% for the test set. But that's not the way we should be doing it.
[18:36] Why? Because in time series analysis, the sequence is very important, the way things are changing
[18:43] together is very important. We can't just pick points from different places or from different
[18:50] times of our data. This is not going to provide good results. And moreover, it's going to bias
[18:57] the results. Now we provide batch size, it's 32. The train loader is we're going to use the data
[19:04] loader for the training data set, or the validation data set and the test data set.
[19:09] And then we create and train a transformer model here. So we're going to define a model
[19:14] time series transformer that we have created. That's a class that we have created
[19:19] previously in this code. We provide the parameters. And as you can see, the sequence
[19:25] length is equal to the one defined here. So that's 30 for now.
[19:31] Same for the prediction length as well. It's equal to one. And if we have a GPU, we're
[19:37] going to use it. Otherwise, we're going to use a CPU trained model is equal to we apply the
[19:45] train transformer model, we provide the model that we have just defined the data, the training data,
[19:51] the validation loader, the learning rate, number of epochs and the device. And that's it. So this
[19:58] is going to take a bit of time, depending on how many epochs you're going to use. So I had to
[20:05] stop it a bit quickly just to get on with the video, the recording, and to show you how we can use the
[20:11] evaluation. So then we just have to call the evaluate model function, we provide the trained
[20:16] model, the test data, the scaler and so on. And as you can see, we have two curves. So
[20:23] this one in blue is the real, these are the real closing prices. And the orange one
[20:30] are the predicted closing prices. And at first, you might say this is working really great. I mean,
[20:38] the predicted closing prices are not very far from the real closing prices. But if you look
[20:45] closely, it looks like the model is a bit copying what happened before in the candle before that.
[20:54] So take, for example, this predicted value, almost equal or a bit higher than the previously
[21:01] real value, the previous real value. Or even better, if you take this line here, so how
[21:07] things changed from this point up to this point, it's a copy and paste of how things
[21:13] changed between these two consecutive points. Same, this change here is translated into this
[21:20] change here. Then the price dropped in reality. And the transformer also dropped the price.
[21:26] Now, it might not be exactly a copy and paste of what just happened in the real price. But to me,
[21:33] it actually looks like the model is just copying how the price is changing very recently. And
[21:42] just replicating this in the future step. It's not really showing any powerful predictive
[21:49] potential. Now, to be fair, at the same time, we didn't provide much for the model. Remember that
[21:55] or the technical indicators we provided to our three technical indicators,
[22:01] we provided the closing prices and so on. So it's not enough to actually come up with a
[22:07] prediction. And the main reason neural networks always fail in this task is because
[22:12] you have a lot of noise in trading data. The price is very jumpy. It's going up and down. It's
[22:19] not showing clear patterns, no repetitive patterns. And so any model that would somehow capture the
[22:27] details will capture noise. And it's going to be very hard for the model to make accurate predictions
[22:34] because it's really drowned and lost in the noise. It's trying to fit noise, basically,
[22:39] more than trying to fit a signal. This is why simpler models tend to perform better in trading. Now,
[22:45] there's a lot to be improved in here. First of all, adding the more technical indicators or
[22:52] custom indicators, if you want, maybe changing the sequence, maybe changing some of these hyper
[22:59] parameters of the model, when you are training the when you are training the model or evaluating
[23:04] the model and so on. So it's a lot to be done, maybe testing this on stocks data rather than
[23:11] forex data, providing the volume centralized volume data and so on. So there's a lot you can
[23:18] change and try to improve with. Don't forget to download the code if you are interested in this
[23:24] part and try to use it for your own experiments. And that's it for this one. I think it was one
[23:30] of the hardest videos I struggled to explain online, but I hope that it still brought you some value
[23:37] and sparked your interest in those in this kind of algorithms. Until our next one, trade safe and see you next time.
