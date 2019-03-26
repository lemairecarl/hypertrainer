function updatePlatform(platform) {
    $.ajax({
        url: "/update/" + platform,
        cache: false
    })
        .done(function( data ) {
            $("table#tasks tr").each(function(){
                value = data[$(this).attr('data-id')];
                $("td[data-col='status']", this).html(value);
                $("td[data-col='status']", this).addClass(value);
            });
        });
}

$( document ).ready(function() {
    $('table').tablesort()
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
    $('tr').click(function() {
        checkbox = $('.toggle-job', this);
        checkbox.prop('checked', !checkbox.prop('checked'));
    });
    $('.toggle-job').click(function(event) {
        event.stopPropagation();
    });
    $('.button').click(function(event) {
        event.stopPropagation();
    });

    updatePlatform('local');
    updatePlatform('helios');
});