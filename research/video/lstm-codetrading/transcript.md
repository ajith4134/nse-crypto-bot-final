# Transcript

language: en (p=0.98)

[00:00] Hi, today we're going to use recurrent neural networks and the LSTM, long for term memory
[00:05] networks for price movements predictions, can be applied for hard stock markets or crypto
[00:10] prices.
[00:11] We're going to write our code in Python and if you're new to this channel, the code
[00:15] can be downloaded from the link in the description below.
[00:18] Looking at the results, the predicted price curve has a similar behavior as the real
[00:22] price movements and this can be very tempting if you are seeing this for the first time
[00:27] and you don't know what's behind this type of prediction.
[00:30] So in this video, we're going to review this together and see if it's worth our investment.
[00:35] So the way we are doing this is first by defining our input parameters and these
[00:39] can be anything from price values, technical indicators and custom indicators
[00:44] that we can include in the data frame.
[00:47] We are looking to predict an output which obviously would be the price
[00:51] movement trend.
[00:52] So in this particular example, just to make things simple,
[00:56] we will try to predict the next candle's closing price.
[00:59] So in other words, if we are using the daytime frame, we would like to predict
[01:04] tomorrow's closing price based on, let's say, the last few days' data.
[01:09] This is an example of how our data is presented in an ethical data frame.
[01:14] So we have the open price, the high, low, close price and the adjusted
[01:18] close price.
[01:19] We have the date as an index in this case and the way the LSTM
[01:23] model works, it takes past data, for example, from the last four days,
[01:28] if this is the daytime frame, and it will try to predict this particular value
[01:33] over here, which is the closing price of the next day.
[01:37] Obviously, before trying the prediction phase, we have to train the model
[01:41] and this is done by providing input and output data for the first set,
[01:45] which we can see here, and the second set of data.
[01:49] Then the third day, for example, we're trying to predict the third day in a row
[01:54] and so on until we reach the end of our training data set.
[01:57] In this example, we're showing only four input days.
[02:01] You can increase this to six days, for example, or any number of days
[02:05] and see how the results are changing.
[02:08] We're going to do this in our price encode.
[02:11] So at the end, the model requires two-dimensional input
[02:15] and our training data set is, in fact, three-dimensional,
[02:18] taking into account the shape of the training data set.
[02:21] If this is not clear for you at the moment, it's fine
[02:24] because we're going to see things in detail in the coding part.
[02:28] We can now let's come to the coding part
[02:30] and see how the model predictions will go.
[02:32] This is our JupyterModel file.
[02:34] We're going to start by importing modules that we are needing.
[02:38] So NAMPA, I have a lot of projects for cutting out curves
[02:42] and pandas TA technical analysis
[02:45] because we need the technical indicators
[02:47] in our data frame as well.
[02:49] And the Yfinance, just to download the data
[02:52] we're going to use for our analysis.
[02:54] So here I'm downloading the Russell 1000 stock
[02:57] starting 2012 up to 2022.
[03:00] So this is 10 years worth of data.
[03:02] This is the daily timeframe.
[03:04] Again, we're using the daily timeframe here
[03:06] because it's less noisy for our algorithm.
[03:09] And this is the data frame that we are obtaining.
[03:12] We have the open, high, low, closing price
[03:14] and the adjusted close price,
[03:16] as well as volume comment that it seems
[03:18] that it contains no valuable data for us.
[03:21] Next step is to add the technical indicators
[03:25] using the TA technical analysis module.
[03:28] So we're using the RSI here
[03:31] and adding this into our data frame as a new column.
[03:34] We have a fast, medium, and slow moving average as well.
[03:38] So the length is 20, 100, and 150.
[03:42] The length of the RSI is 16.
[03:45] You can, of course, change these parameters
[03:47] and add other technical indicators to your liking.
[03:50] So this is why I'm sharing the notebook file.
[03:53] You can modify the Python code as you wish.
[03:56] Then I'm adding my target column into my data frame.
[04:00] So there are three ways of doing this.
[04:02] It's either we are checking the distance of price
[04:06] between the current open and the future close price,
[04:09] and we can proceed using classification approach,
[04:11] checking if we are going up or down, for example,
[04:14] in which case you have one of two values,
[04:17] either one or zero, but we're not going to use this
[04:20] for this video, so we can comment these three lines.
[04:23] What we are interested in here is the target next close,
[04:27] which is just the next closing price
[04:29] or the closing price of the next day.
[04:31] And this is obtained just by using the adjusted close column
[04:36] and shifting it with an index minus one.
[04:39] And after doing this, we can drop empty values, empty rows.
[04:44] We can reset the index, and also we can drop the volume,
[04:48] the closing column, and the date column
[04:51] because we don't need them for this study.
[04:53] At this point, our data frame looks like this.
[04:56] We have the open, high, low, then the adjusted close
[04:59] because we dropped the closing price.
[05:01] We don't need it.
[05:02] The RSI, the fast-moving average, the medium-moving average,
[05:06] and the slow-moving average columns.
[05:08] Then we have the target, target class,
[05:10] and the target next close,
[05:12] and this is the one we're going to use and try to predict.
[05:15] So we're going to train our model to predict this particular column.
[05:18] If we take a look at these values,
[05:20] here we have 787.79,
[05:23] so this is nothing but the adjusted close of the next column.
[05:28] So this is what we can see here, 787.79.
[05:31] Then we will apply a scalar to our data
[05:34] because we're using the network,
[05:36] so our data should be between 0 and 1,
[05:39] and this is easily done by using the min-max scalar
[05:42] of the scikit-learn packet.
[05:44] So this is the way we can do it.
[05:46] So min-max scalar applied to the feature range
[05:50] between 0 and 1,
[05:51] and I'm going to fit the data,
[05:54] fit and transform the data,
[05:56] which is called data set,
[05:57] which is my data frame here,
[05:59] using this particular scalar.
[06:01] And what we obtain from this is a two-dimensional array.
[06:05] It's a NumPy array because the scalar
[06:08] is going to transform our data frame,
[06:10] our Pandas data frame into a NumPy array,
[06:12] which factors our scale between 0 and 1.
[06:15] So we have to keep in mind that the columns
[06:18] are still kept within this array.
[06:20] However, we have to remember which is the first one,
[06:23] the second one, and so on
[06:24] just to make sure that we are seeding the model
[06:26] with the correct data.
[06:28] So our data at this point looks like this.
[06:31] We need to discard the last three columns
[06:35] from our input data
[06:37] because we want to see them
[06:39] with the open action,
[06:41] the adjusted closing price,
[06:43] and the RSI, the three moving averages,
[06:46] and then we would like to predict
[06:48] the target or the target next close,
[06:50] whatever we want to predict.
[06:52] So my input data is composed of
[06:54] one, two, three, four, five, six, seven,
[06:57] eight columns in total
[06:59] because after that is what my model
[07:01] is supposed to be predicting.
[07:03] So we will feed the input
[07:05] as the first eight columns
[07:07] and then we will choose the target
[07:09] next close column to be predicted.
[07:11] And this is done in the cell.
[07:13] The number of back candles
[07:15] is the number of candles or days
[07:17] you want to look back in the past
[07:19] just to predict what will be coming tomorrow
[07:22] or the closing price of tomorrow's candle.
[07:25] So in the example,
[07:27] I started by four, then I gave D9.
[07:30] Number six, for example,
[07:32] so we can try here to read the past 10 days
[07:35] and we consider that 10 days data
[07:37] should be enough to predict
[07:39] the next candle's closing price.
[07:41] Then we're going to process
[07:43] the eight columns data,
[07:45] as we have explained.
[07:47] We're going to put these into the X,
[07:49] which is our input data for the model.
[07:51] Then we predict the data,
[07:53] the target data, which is the Y,
[07:55] is one of the columns we're going to choose.
[07:57] So here I'm choosing the last column,
[07:59] column index minus one,
[08:01] which is this target next close.
[08:04] In other words, the closing price
[08:06] of the next day.
[08:08] So here also for the coding
[08:10] style in Python,
[08:12] you can summarize all of this cell
[08:15] into one line of comprehension.
[08:17] These are the Python lists,
[08:20] it works very nicely
[08:22] and it's written in a very ancient way.
[08:24] So I'm not going into detail here in this video
[08:26] because it's not the purpose of what we're doing.
[08:28] I just kept it for you
[08:30] if you are interested in the coding part.
[08:32] So now if we take a look at the shape of X,
[08:35] we have eight columns.
[08:37] This is what we considered.
[08:39] We have eight columns,
[08:41] including our technical indicators,
[08:43] and this is what we have added into our data frame.
[08:45] And we have ten back candles,
[08:48] second dimension because we considered
[08:50] ten back candles for the model as an input.
[08:53] And we have 2,437 rows,
[08:57] and this is dependent on the size of our data frame.
[09:00] So if we took ten years
[09:02] and we cleaned the data later on,
[09:04] what is left for us is 2,437 rows.
[09:10] This is a very tricky part
[09:12] because if you see the LSTM model
[09:14] with the wrong dimensions,
[09:16] it's not going to work.
[09:18] So you should always verify
[09:20] how is the shape of your data,
[09:22] what did you include in the input
[09:24] and the output data.
[09:26] We can try and print X as well,
[09:28] just to take a look at how it looks like.
[09:30] So we have a three-dimensional array.
[09:32] It's an entire array.
[09:34] And if we can print Y as well,
[09:37] we can have a look at it.
[09:39] So this one is a one-dimensional array.
[09:42] Actually, it's a two-dimensional array,
[09:44] each element contains only one single value.
[09:47] So this is the correct format.
[09:49] This is the trickiest part
[09:51] is to guess what kind of shape
[09:53] is compatible with your model
[09:55] that we are going to train later on.
[09:57] And at this point, we can split our data
[09:59] between the training and the testing data.
[10:02] So 80% of my data
[10:04] is going to be for my training
[10:06] or training the model
[10:07] and I'm leaving 20% for testing the model.
[10:10] Now we can include the correct package
[10:12] and some of the models that are needed
[10:14] for training our LSTM models.
[10:16] Some of these are redundant
[10:18] so we don't have to open copying and pasting these lines.
[10:20] Some of my codes can try and demand
[10:23] to see different results.
[10:25] And we are using TensorFlow and Keras,
[10:28] in this case.
[10:29] And notice that my input variable here,
[10:32] we're using the input function
[10:34] and the shape is equal to the number of bulk handles,
[10:37] meaning the number of rows I'm treating my model with
[10:40] and the number of columns.
[10:42] So this is a two-dimensional input shape matrix
[10:45] that we have to see for our model
[10:48] in the training part,
[10:49] but also in the prediction part.
[10:51] And I'm using an intermediate layer of nodes
[10:54] and we have 150 nodes,
[10:57] then one dense layer,
[10:59] one node before proceeding to the output of my result.
[11:03] So the model includes all of these layers
[11:06] and this is indicated here in this particular line.
[11:09] I'm using the add-on optimizer.
[11:11] I'm not going into details in this video.
[11:14] And then I'm compiling the whole model
[11:16] and we can start setting the models,
[11:18] using it with the training data,
[11:20] the input data and the training output data
[11:23] or the value to be predicted.
[11:25] Depending on the parameters of the model
[11:27] the number of layers,
[11:28] the number of nodes,
[11:30] the number of epochs and so on,
[11:32] it might take a while before the model is trained.
[11:34] So here I chose very simple parameters
[11:36] and I have used a small model,
[11:39] relatively simple model,
[11:40] so it's not going to take much time.
[11:42] And after the model is trained,
[11:44] we can try to predict using the same model
[11:47] but feeding it with the X underscore test,
[11:50] which is the testing part,
[11:52] meaning the part of the data that the model didn't read yet.
[11:55] So we trained the model on the training data
[11:58] when we split our data into training and testing parts.
[12:02] So the 80% were used for training
[12:04] and the test, which is the 20% of the data,
[12:08] was checked now for the predictions.
[12:10] So we can try to predict the Y part,
[12:14] the Y variable,
[12:15] meaning the next day's closing price.
[12:18] And I'm just printing the first 10 values here
[12:21] between the predicted value
[12:23] and the read value that should be predicted.
[12:26] So at first we cannot compare numbers
[12:29] visually like this,
[12:31] so we can plot these
[12:32] and I'm going to re-plot what we have seen here.
[12:35] And this is the result we are obtaining so far.
[12:38] And this is where things become interesting, actually.
[12:41] So we can see that we have a very similar curve
[12:44] to our data.
[12:46] So we can have the first impression
[12:48] that there is some kind of nice predictions happening there.
[12:51] And the first thing I'm going to do is to go back
[12:55] and instead of feeding the model with the last 10 days data
[12:59] and asking the model to predict one more value,
[13:02] I'm going to feed it with 30 days.
[13:05] So in other words,
[13:06] the model is going to read what happened in the last 30 days
[13:10] and then is going to try to predict tomorrow's closing price.
[13:14] So let's run this back and see what it will be giving.
[13:19] So I retrained the model using 30 back candles
[13:22] and we're going to see the predictions,
[13:25] predictions looking even closer to the real data,
[13:29] in this case, to the market prices.
[13:31] And if you are interested in this,
[13:33] you can go back and change the number of layers.
[13:37] You can add additional layers, additional nodes in here,
[13:40] and you can as well actually go back to the beginning
[13:45] and try to add new technical indicators.
[13:48] I mean, I just used four technical indicators here,
[13:52] the ISI and three percent moving averages.
[13:55] It would be interesting to check how the model behaves.
[13:58] If also we provide the slope of the moving averages,
[14:01] if they are positive or negative,
[14:03] I mean going upwards or downwards and so on,
[14:07] and maybe adding momentum column
[14:11] and other technical indicators
[14:13] that we assume might be useful in this case.
[14:16] Actually, there is much more there.
[14:18] There's a small clap in these results
[14:20] and I'm going to keep this video as short as possible.
[14:23] In the next video, I'm going to discuss the results
[14:26] and we're going to rerun things in a more clear way,
[14:29] showing where this model is failing
[14:32] and why it shouldn't be used as is to predict the market.
[14:36] That being said, some improvements might be done.
[14:39] Once you understand the failures of the model,
[14:42] it's always interesting because we can apply the corrections.
[14:45] So stay tuned for the next one
[14:47] and until our next video, play safe and see you next time.
