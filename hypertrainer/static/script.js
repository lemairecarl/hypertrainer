function updatePlatform(platform) {
    $.ajax({
        url: "/update/" + platform,
        cache: false
        //timeout: 25000
    })
        .done(function( data ) {
            if( Object.keys(data).length == 0 ) return;
            for (var task_id in data) {
                row = $("tr[data-id='" + task_id + "']")
                row_data = data[task_id]
                // Status
                status = row_data['status'];
                $("td[data-col='status']", row).html(status).removeClass('updating').addClass(status);
                // Epoch
                $("td[data-col='epoch']", row).html((row_data['epoch'] + 1) + ' / ' + row_data['total_epochs']).removeClass('updating');
                // Iteration
                $("td[data-col='iteration']", row).html(row_data['iter']).removeClass('updating');
                if (row_data['epoch'] > 0) {
                    // Total time remain
                    $("td[data-col='total_time_remain']", row).html(row_data['total_time_remain']).removeClass('updating');
                    // Epoch time remain
                    $("td[data-col='ep_time_remain']", row).html(row_data['ep_time_remain']).removeClass('updating');
                } else {
                    // First epoch, cannot compute remaining time
                    $("td[data-col='total_time_remain']", row).empty().removeClass('updating');
                    $("td[data-col='ep_time_remain']", row).empty().removeClass('updating');
                }
            }
        })
        .fail(function( jqXHR, textStatus ) {
            console.log('Update request has failed: ' + textStatus);
            console.log(jqXHR);
        });
}

function filterTable() {
    filter = $("#search-box input").val().toUpperCase();
    // Loop through all table rows, and hide those who don't match the search query
    num_results = 0;
    $("table#tasks tr.task-row").each(function() {
        show = false;
        $("td", this).each(function() {
            if ($(this).text().toUpperCase().indexOf(filter) > -1) {
                show = true;
            }
        });
        if (show) {
            $(this).show();
            num_results += 1;
        } else {
            $(this).hide();
        }
    });
    if (num_results == 0) {
        $("#search-box").addClass('error');
    } else {
        $("#search-box").removeClass('error');
    }
}

$( document ).ready(function() {
    $('#project-selector')  // For display
        .dropdown({
            action: function(text, value) {
                p_arg = (value != '') ? '&p=' + value : '';
                window.location.replace('/?action=chooseproject' + p_arg)
            }
        })
        .dropdown('set selected', $('#project-selector').attr('data-selected'));
    $('#project.dropdown')  // For new task submission
        .dropdown({
            allowAdditions: true
        })
        .dropdown('set selected', $('#project-selector').attr('data-selected'));
    $('#platform.dropdown')
        .dropdown('set selected', 'local');
    $('button#new-task').click(function() {
        $('#submit-dialog').modal({
            onApprove : function() {
              $('#form-new-task').submit();
            }
        }).modal('show');
    });
    $('table').tablesort();
    $('thead th.number').data(
        'sortBy',
        function(th, td, tablesort) {
            return parseFloat(td.text());
        }
    );
    $('#checkall').click(function(event) {
        $('.toggle-job').prop('checked', $(this).prop('checked'));
        event.stopPropagation();
    });
    $('tbody tr').click(function() {
        // checkbox = $('.toggle-job', this);
        // checkbox.prop('checked', !checkbox.prop('checked'));

        // Handle new selection
        $('#monitoring').html('<div class="ui active loader"></div>');
        $('#monitoring').load('/monitor/' + $(this).attr('data-id'));
        $('.selected').removeClass('selected');
        $(this).addClass('selected');
    });
    $('.toggle-job').click(function(event) {
        if ($('.toggle-job:checked').length > 0) {
            $('form#bulk button').removeClass('disabled');
        } else {
            $('form#bulk button').addClass('disabled');
        }
        event.stopPropagation();
    });
    $('.button[type=submit]').click(function(event) {
        $(this).addClass('loading');
    });
    $('td.updating').append('<div class="ui active tiny inline loader"></div>');
    $("#search-box input").keyup(function() {
        filterTable();
        $('.toggle-job').prop('checked', false);
    });

    // Update table
    $.ajax({
        url: "/enum",
        cache: false
    })
        .done(function( platform_names ) {
            platform_names.forEach(function(p){
                updatePlatform(p);
            });
        });
});