.. _secCallbacksC1:

Modifying Solver Behavior - Callbacks
-------------------------------------

.. c:function:: int GRBcbsetdblparam(void *cbdata, const char *paramname, double newvalue)

   Set a double-valued parameter from within a callback.

   :return value: Zero if successful.
   :arg cbdata: The ``cbdata`` argument that was passed into the user callback.
   :arg paramname: The name of the parameter.
   :arg newvalue: The desired new value for the parameter.

.. c:function:: int GRBcbsetintparam(void *cbdata, const char *paramname, int newvalue)

   Set an int-valued parameter from within a callback.

   :return value: Zero if successful.
   :arg cbdata: The ``cbdata`` argument that was passed into the user callback.
   :arg paramname: The name of the parameter.
   :arg newvalue: The desired new value for the parameter.

.. c:function:: int GRBcbcut(void *cbdata, int cutlen, const int *cutind, const double *cutval, char cutsense, double cutrhs)

   Add a cutting plane to the MIP model from within a callback.

   :return value: Zero if successful.
   :arg cbdata: The ``cbdata`` argument that was passed into the user callback.
   :arg cutlen: The number of non-zero coefficients in the new cutting plane.

.. c:function:: void GRBterminate(GRBmodel *model)

   Request that the optimization stop as soon as possible.

   :arg model: The model to be terminated.
