/* fastops.c — hot numeric kernels for the network (polyglot rule, §10).
 *
 * Compiled to a shared lib, called from Python via ctypes (fastops.py has
 * pure-Python fallbacks). Build:  bash native/build.sh
 */
#include <math.h>
#include <stdlib.h>

/* Squared Euclidean distances from query q to each of n rows (d dims). */
void sqdists(const double *X, int n, int d, const double *q, double *out) {
    for (int i = 0; i < n; i++) {
        const double *row = X + (long)i * d;
        double s = 0.0;
        for (int j = 0; j < d; j++) { double e = row[j] - q[j]; s += e * e; }
        out[i] = s;
    }
}

/* Full logistic-regression training: `epochs` of full-batch gradient descent.
 * w (len d) and *b are updated in place. */
void logreg_train(const double *X, const double *y, int n, int d, int epochs,
                  double lr, double *w, double *b) {
    double *grad = (double *)malloc(sizeof(double) * d);
    if (!grad) return;
    for (int ep = 0; ep < epochs; ep++) {
        for (int j = 0; j < d; j++) grad[j] = 0.0;
        double gb = 0.0;
        for (int i = 0; i < n; i++) {
            const double *row = X + (long)i * d;
            double z = *b;
            for (int j = 0; j < d; j++) z += w[j] * row[j];
            double p = 1.0 / (1.0 + exp(-z));
            double e = p - y[i];
            for (int j = 0; j < d; j++) grad[j] += e * row[j];
            gb += e;
        }
        for (int j = 0; j < d; j++) w[j] -= lr * grad[j] / n;
        *b -= lr * gb / n;
    }
    free(grad);
}

/* Full 1-hidden-layer MLP training (tanh hidden, sigmoid out), full-batch GD.
 * W1 is row-major H*d, b1 len H, W2 len H, *b2 scalar — all updated in place. */
void mlp_train(const double *X, const double *y, int n, int d, int H, int epochs,
               double lr, double *W1, double *b1, double *W2, double *b2) {
    double *gW1 = (double *)malloc(sizeof(double) * H * d);
    double *gb1 = (double *)malloc(sizeof(double) * H);
    double *gW2 = (double *)malloc(sizeof(double) * H);
    double *ha  = (double *)malloc(sizeof(double) * H);
    if (!gW1 || !gb1 || !gW2 || !ha) { free(gW1); free(gb1); free(gW2); free(ha); return; }
    for (int ep = 0; ep < epochs; ep++) {
        for (int k = 0; k < H * d; k++) gW1[k] = 0.0;
        for (int j = 0; j < H; j++) { gb1[j] = 0.0; gW2[j] = 0.0; }
        double gb2 = 0.0;
        for (int i = 0; i < n; i++) {
            const double *row = X + (long)i * d;
            for (int j = 0; j < H; j++) {
                const double *w1j = W1 + (long)j * d;
                double pre = b1[j];
                for (int k = 0; k < d; k++) pre += w1j[k] * row[k];
                ha[j] = tanh(pre);
            }
            double o = *b2;
            for (int j = 0; j < H; j++) o += W2[j] * ha[j];
            o = 1.0 / (1.0 + exp(-o));
            double dd = o - y[i];
            gb2 += dd;
            for (int j = 0; j < H; j++) {
                gW2[j] += dd * ha[j];
                double dh = dd * W2[j] * (1.0 - ha[j] * ha[j]);
                gb1[j] += dh;
                double *gw1j = gW1 + (long)j * d;
                for (int k = 0; k < d; k++) gw1j[k] += dh * row[k];
            }
        }
        *b2 -= lr * gb2 / n;
        for (int j = 0; j < H; j++) {
            W2[j] -= lr * gW2[j] / n;
            b1[j] -= lr * gb1[j] / n;
            double *W1j = W1 + (long)j * d;
            double *gw1j = gW1 + (long)j * d;
            for (int k = 0; k < d; k++) W1j[k] -= lr * gw1j[k] / n;
        }
    }
    free(gW1); free(gb1); free(gW2); free(ha);
}
