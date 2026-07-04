# Transcript

language: en (p=0.99)

[00:00] Hi. In this video we're going to use neural networks to build a simple trading model.
[00:06] In the previous video we tried to build a machine learning model and fit it into our data for trend predictions.
[00:12] For that we have used the x-gradient boosting and if you haven't watched that video it would be easier if you do so before following this one.
[00:21] Because the Python code will be almost the same only instead of using the xjboost model we're going to use a neural network model.
[00:29] Now in the previous video we saw that machine learning was not the best idea to predict the trend directions
[00:35] although someone proposed that it works best in the direction of the trend and it's not as good as understanding trend reversals.
[00:43] And actually this is what we were trying to do. The way we built the model we were trying to predict trend reversals
[00:50] that for some reason this comment is very much true, it's very convincing, something that we should be taking into account in the future.
[00:57] Thanks to whoever wrote this comment and to be honest I haven't thought about it this way
[01:02] so it might be worth to check how to correct this and improve our models in the future.
[01:07] The idea in this video follows almost the same steps of the previous video.
[01:12] So using neural networks we have input features for example the RSI could be one, the moving average slope, the parabolic SAR slope
[01:20] and any custom strategy signal as we have used in the previous video.
[01:25] With neural networks of course we can use as many input features as we like
[01:30] and here we're going to include the same strategy signal that we have built and used in the previous video with the x-gradient boosting model.
[01:38] The reason we are using this custom strategy signal is that it provided positive returns in a classical passive strategy
[01:48] so we expect it to be a good addition to machine learning or neural networks
[01:53] and also to be able to compare for the sake of comparison because we have already used it in the XJ Boost model in the previous video
[02:01] so to compare XJ Boost versus neural networks somehow we have to use the same input parameters.
[02:07] If you haven't watched the previous videos about this particular custom strategy signal
[02:12] in brief it's an indicator that uses support and resistance levels
[02:16] along with price movements and candlestick patterns to detect reversals in the trend
[02:21] and since the signal provided good returns in a classic passive strategy
[02:26] we decided to use it in machine learning to test somehow if it would be a good addition as an input feature for these particular models.
[02:34] In this video it's part of our input features for the neural network model that we are going to build.
[02:41] The model we're using is a neural network classifier so we project to predict if the trend is going to be up or down
[02:49] by providing one of two categories, either one or zero.
[02:54] The main challenge in such models is to guess how many hidden layers you would have to include between the input features
[03:02] and the final output results.
[03:04] This can be anything from one layer up to a large number of layers.
[03:09] Another challenge as well is to find an optimal number of nodes for each of these hidden layers
[03:15] and these numbers are very much open.
[03:18] In the model you can have something between one hidden layer up to let's say 100 layers
[03:24] or one node up to I would say 10 to 100 nodes for such a model.
[03:30] So there's no really clear rule to predict what would be the optimal number of nodes and layers that would give you the best result.
[03:38] In most of the cases these two parameters are decided based on the method of trials and errors
[03:44] relying also on the expertise of the data scientist who is building the code.
[03:49] Okay, now let's see how to write this in Python and have an idea about what to expect from such type of models.
[03:55] As usual our code is a Dr. Marburg file.
[03:58] I will leave a link in the description of the video so you can download it and experiment on these models on your own.
[04:04] The first cell is simply reading the data.
[04:07] We've been using the same data pretty much on most of the videos so far.
[04:12] So we're loading the euro-us dollar daily data between 2003 and 2021.
[04:17] We're cleaning the data and we're going to spend much time on this
[04:21] and these are the support and resistance functions that we have used in more than two videos previously
[04:26] so they are detailed in other videos on how to detect support and resistance functions automatically in Python.
[04:33] Then we have the functions that we use to detect the specific candlestick patterns
[04:37] like the engulfing pattern of the rejection pattern, shooting stars and stuff like that.
[04:41] So all of these were already defined and detailed in previous videos.
[04:45] I'm not going to spend a lot of time on this for now.
[04:48] In brief we are detecting support and resistance levels and we are detecting also when we have the specific candlestick patterns
[04:56] or rejection patterns that are happening close enough to support and resistance levels.
[05:02] In which case we are expecting the market to be in reversal of a trend
[05:06] and we will base our trading on this assumption.
[05:09] Now we're choosing the features, the columns so we have the open, high, low, close, the volume
[05:14] and our custom signal that we have just coded.
[05:18] We will build the strategy and test our past strategy first
[05:23] so I'm not going to explain it again because it was explained a couple of times in previous videos.
[05:28] I just included this here for the sake of verification
[05:31] so the strategy is providing 126% return as a total return of value
[05:38] and this is just to make sure that the provided signal is working properly.
[05:42] So far there are no surprises, everything is proper.
[05:45] We have an increasing equity as you can see here over the years
[05:49] and the signal is the promising signal to detect trend reversals.
[05:54] And we have our target because it's the supervised model that we are training here.
[05:59] In this case we need to know already if the trend is going up
[06:04] or is it reversing up or reversing down.
[06:07] And this is tested in this particular function here.
[06:10] If the price is going up starting from a certain candlestick looking let's say 10 days in the future
[06:17] and touching plus 250 pips it means we have an uptrend.
[06:21] If it touches minus 250 pips in this case we have a downtrend.
[06:26] If it touches both we don't know so we return zero as a category.
[06:30] If it touches neither meaning it stays between plus or minus 250 pips
[06:35] we also return zero because we don't have a clear trend in this case.
[06:39] So at this point I can use this function looking 30 days in the future
[06:43] and fixing my parameter of the difference to 250 pips
[06:48] and the stop loss take profit ratio to 1
[06:51] so it means that the distance to the take profit is the same as the distance to the stop loss value.
[06:57] And in this histogram we can see the distribution of the three different categories of our trends.
[07:02] So we have very little let's say 750 cases or a frequency of 750 where we have category zero.
[07:10] It means no clear trend.
[07:12] We have a downtrend.
[07:14] It's showing 1750 and the most frequent trend is an uptrend
[07:19] which is category two. It's around 2000 something.
[07:23] So in this histogram of frequencies of categories
[07:27] will help us interpret better the final result.
[07:31] I'm going to use the RSI just like we have used in the previous video for the X-WOOST
[07:35] and at this point our data frame would look like this.
[07:39] We have the open, high, low, close price, the volume of the trace.
[07:42] We have our custom made signal.
[07:45] We have the target that we have just executed here.
[07:49] It's a function called myTarget and we have the column showing the RSI.
[07:53] One more time our data frame needs a small cleaning procedure
[07:57] because the RSI needs for example 20 or 14 depending on what parameters you are using.
[08:02] Here we are using a length of 16 so we need at least 16 days at first
[08:08] or 16 euros to be able to obtain our first RSI value.
[08:12] The rest will be none.
[08:15] At the end of the data frame our target will show none also
[08:18] because we are looking 30 days in the future
[08:21] and in this case if these 30 days or 30 euros are not available
[08:25] it's not possible to predict any trend at the end of our data frame.
[08:29] I'm going fast on these parts of the code
[08:32] because we have already seen these in detail in the previous video.
[08:36] So I strongly recommend that you watch that video first
[08:39] and then coming to this video things will be much clearer.
[08:42] At this point we can proceed with something called one-hubbing coding.
[08:46] Regarding the signal categories it's basically splitting the results
[08:50] of the custom made signals into three different columns
[08:54] whether we have a category 0 or a signal 0, 1 or 2.
[08:59] In this case we are going to put one for the corresponding signal category
[09:03] and zeros for the other two categories.
[09:06] At this point I will skip this part of the code
[09:09] which is the previous video's part.
[09:11] It's the X gradient boosting classifier.
[09:14] I left it here just for reference in case you wanted to download
[09:17] both models in one single file.
[09:20] And I'm going to move for the next model
[09:23] which is the neural networks model.
[09:25] I'm going to import from scikit-learn
[09:28] something called neural underscore network
[09:31] and the MLT classifier.
[09:34] So we need the classifier because our problem
[09:37] is a classification problem.
[09:39] We need to guess which category the trend will fall in.
[09:42] Is it category 0, 1, or category 2?
[09:45] Is the trend going up, down, or we don't know.
[09:48] It's simply a third category.
[09:50] We're going to split our data 60% for training
[09:54] and 40% for testing or validating the model.
[09:59] Once our data is split into X-tests
[10:03] and Y-train Y-test,
[10:05] remember that the X part contains the attributes
[10:08] of the input features of the model
[10:11] and these would be the RSI, the signal category 0, 1, and 2 columns.
[10:16] And the Y is going to be our target,
[10:19] the trend direction or the predicted trend direction.
[10:22] So I'm calling a variable called n here.
[10:24] We're calling the function MLT classifier
[10:27] using the hidden layer sizes parameter
[10:30] to include 20 nodes on the first layer,
[10:33] 20 nodes on the second layer,
[10:35] 10 nodes for the third and 10 nodes for the fourth layer.
[10:38] Now, if you want, it's easier to start with simply two layers
[10:42] and for this we can simply delete the other two layers.
[10:46] So now we have two layers.
[10:48] Let's say two hidden nodes in the first hidden layer
[10:51] and another two hidden nodes in the second hidden layer.
[10:55] The random state is simply a seed for a random starting state.
[10:59] It doesn't matter in our case.
[11:01] You can put a 10, 100, or whatever.
[11:03] The verbosity is equal to 0.
[11:05] For now, we don't need it.
[11:06] Maximum iteration is 1,000.
[11:08] The last parameter is our activation function.
[11:11] So for these, you have to go through a course
[11:14] of neural networks to understand what are the differences
[11:17] between the different activation functions.
[11:19] However, here in our case for this particular application,
[11:23] it doesn't change much,
[11:25] so we're going just to go for a default reload function.
[11:28] Then we can fit our model.
[11:30] So an n dot fit using x-train,
[11:33] so the x of the training set
[11:35] and the y of the training set as well.
[11:37] Now, after we have fit our model,
[11:39] we can start the prediction part
[11:41] and we're going to predict first the training set.
[11:44] We're going to feed the x underscore train
[11:47] to predict the training set
[11:49] which we already fed for the model for the fitting part
[11:52] to see how good is the model fitting within the training data.
[11:56] Then we're going to do the same.
[11:57] We're going to predict for the test set,
[12:00] also feeding the x underscore test
[12:02] as a parameter for the model.
[12:04] And we're going to compute the accuracy score
[12:07] for both the training set predictions
[12:10] and the test set predictions.
[12:12] Here in this part, we are simply printing the results.
[12:15] And in this case, you can see
[12:17] that we have 52.6% accuracy
[12:20] for the training result predictions
[12:22] and 33.17% for the test results.
[12:26] Now, these were on a bigger number of hidden layers
[12:30] and we're here on these with 2x2.
[12:34] Just the modifications, we get pretty much the same,
[12:37] so 51.86% and 32.85%.
[12:41] As a global score, this is not something
[12:43] we can rely on for training.
[12:45] Remember, we have 32%,
[12:47] and the take profit and the stop loss
[12:49] are at equal distances from the price.
[12:52] We took plus or minus 250 bits.
[12:55] So our stop loss take profit ratio,
[12:57] defining the target is equal to 1.
[13:00] So we need something that is larger
[13:02] than, let's say, 45 to 50%,
[13:05] because we have three different categories
[13:07] to ensure that it might be a good indicator,
[13:10] it might be a good model
[13:11] for positive returns in trading.
[13:13] Now, just as we have discussed in the previous video,
[13:16] you might have a very naive model
[13:19] that chooses the most frequent category all the time.
[13:22] For example, here it's the category of the uptrend,
[13:24] meaning equal to, as you can see,
[13:27] on the histogram from our data.
[13:29] So if I have a model choosing 2 all the time,
[13:32] this model will at least have 34 or 35% of accuracy
[13:37] in any case.
[13:39] But it's not really a prediction model.
[13:41] It's a very naive model that doesn't work for trading.
[13:44] We can plot the confusion matrix
[13:46] or print the confusion matrix
[13:48] in a classification report.
[13:49] And immediately from looking at the confusion matrix,
[13:52] we can see that our model is predicting
[13:55] one single category all the time.
[13:57] The other categories are simply nonexistent in this case.
[14:01] This is an indicator that it's not working properly.
[14:04] We're not predicting really anything
[14:06] using this particular model.
[14:07] Now, one modification that we can start applying
[14:10] is increasing the number of nodes.
[14:13] Let's say we have four input features
[14:16] for different columns.
[14:17] In this case, the RSI Category 01 and 02.
[14:21] We have to have at least four or even the double.
[14:23] Let's take eight, for example.
[14:25] Let's add another hidden layer, which is equal to eight.
[14:28] Maybe one that is equal to four.
[14:30] Before going down to three, which is our output result,
[14:35] the three different categories that we are trying to predict.
[14:38] And even now, actually, we still have almost the same results.
[14:42] So 51.8, 32.8%.
[14:45] And then we are checking the in-depth confusion matrix
[14:50] of the model, and still the model is choosing one category
[14:53] over the rest of the categories all the time.
[14:56] So we have zero precision for categories 01 and 01,
[15:00] and we have zero precision on the test set
[15:02] also for the same two categories 01.
[15:05] The only working category is 02,
[15:07] which is providing 0.33% of precision.
[15:10] That equals, obviously, 100%,
[15:13] because all the cases we are simply saying
[15:15] that it's category 02.
[15:17] Now, let's try to increase this number
[15:20] to something that is larger,
[15:22] maybe making the model more complex.
[15:24] So let's go 20 by 20.
[15:27] Maybe, I don't know, 50, and then dropping down to 30.
[15:31] And from 30, we go to three, which is our final result.
[15:35] To fight on this, first of all,
[15:37] it's going to take more time to fit,
[15:40] usually the more layers and the more nodes
[15:42] you include in your model, the more complex it becomes,
[15:45] the more computing power it will require to fit and to predict.
[15:49] But in this case, we don't have a very large data set,
[15:52] so it's not much of a problem for this video.
[15:56] And again, we try to compute this part,
[15:59] and now our model is starting to predict something
[16:03] for the category 01 sometimes,
[16:06] instead of choosing all the time category number two.
[16:09] So in other words, we were using a very low complexity model
[16:13] at first, and now it's going a bit better.
[16:16] However, the recoil is still very low.
[16:19] In this case, it's 35%.
[16:21] In other words, we are missing out 95% of the situations
[16:26] where we have a downtrend in the market.
[16:28] So the model is not guessing these right.
[16:30] It's not as sensitive as it should be
[16:32] for this particular category,
[16:34] which is the downtrend category.
[16:36] So in this case, I'm going to try to make it
[16:39] even more complex.
[16:40] Let's go up to 50 here,
[16:43] and 50 going up to 60, then 30.
[16:48] And maybe, I don't know, maybe we can try
[16:50] to implement something like 9 here in between
[16:54] and run this one more time.
[16:57] And we can see that globally it's the same accuracy,
[17:00] but we have something higher as the test result.
[17:03] It's around 35%.
[17:05] Let's check the in-depth analysis.
[17:07] So we have more predictions
[17:09] regarding the other categories.
[17:11] So the downtrend, now the recoil is 0.13.
[17:14] So it's improving, and we have a precision 0.61,
[17:18] meaning 61% of the times we were correct
[17:21] regarding this downtrend behavior.
[17:24] For the uptrend, it's always 0.33.
[17:26] So it's 33% with the recoil 0.93.
[17:30] As you can see, it's very much a trial and error.
[17:33] You can go on and on by trying
[17:35] a different number of layers, different number of nodes.
[17:37] Now, I know some of the viewers on this channel
[17:40] are probably experts on your networks
[17:42] and machine learning models.
[17:44] If you have any advice or any book
[17:47] that you would recommend
[17:48] or the choice of the number of layers
[17:50] and the number of nodes,
[17:51] particularly in this type of problem,
[17:54] it would be nice if you could drop a comment.
[17:56] I would be really keen to know what do you think about this,
[17:59] where we are hesitating about the number of layers,
[18:02] number of nodes, and so on.
[18:04] And we can see that the results are very much affected
[18:07] by the complexity of the model
[18:09] and modifications we can apply on these hyperparameters.
[18:12] So if you have any advice at all in this regard
[18:15] or a book to recommend,
[18:17] I would be really interested in knowing
[18:19] what do you think about it,
[18:21] what are your inputs on this particular topic.
[18:24] Finally, we could attempt to compare the results
[18:27] obtained by our neural networks classifier
[18:30] and the previous model,
[18:31] which is the x-gradient boosting model
[18:33] that we have used in the other video.
[18:35] I believe at this point,
[18:37] the machine learning model,
[18:38] the classical machine learning,
[18:40] is working best from this perspective
[18:43] because we have both categories
[18:45] represented in the training set
[18:47] and in the prediction set.
[18:49] However, if we look at the global results
[18:51] in the training accuracy and the test accuracy,
[18:54] they are almost the same.
[18:56] I mean, neural networks
[18:57] or classical machine learning model
[18:59] could provide us with the same results
[19:01] in this particular application.
[19:03] Remember that we are using the
[19:05] SKLearn MLP classifier,
[19:07] which is considered a relatively simple
[19:09] neural network model.
[19:11] There are more advanced models
[19:13] using TensorFlow and Keras as an interface.
[19:16] And that's all I had to tell you on this topic.
[19:18] I hope you guys liked it
[19:20] and found the information helpful.
[19:22] Wishing you the best for the new year
[19:24] and see you next time.
