# Modifying Solver Behavior - Callbacks

int GRBcbcut(void *cbdata, int cutlen, const int *cutind, const double *cutval, char cutsense, double cutrhs)

   Add a cutting plane to the MIP model from within a callback.

   Return value:
      Zero if successful.

   Parameters:
      * **cbdata** – The "cbdata" argument that was passed into the
        user callback.

      * **cutlen** – The number of non-zero coefficients in the new
        cutting plane.
